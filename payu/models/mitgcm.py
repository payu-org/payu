"""payu.models.mitgcm
   ==================

   Driver interface to the MITgcm ocean model.

   :copyright: Copyright 2011 Marshall Ward, see AUTHORS for details
   :license: Apache License, Version 2.0, see LICENSE for details
"""

# Standard Library
import errno
import os
import sys
import shlex
import shutil as sh
import subprocess as sp

# Extensions
import f90nml
import yaml

# Local
from payu.fsops import mkdir_p
from payu.models.model import Model


class Mitgcm(Model):

    def __init__(self, expt, name, config):
        super(Mitgcm, self).__init__(expt, name, config)

        # Model-specific configuration
        self.model_type = 'mitgcm'
        self.default_exec = 'mitgcmuv'

        self.restart_calendar_file = self.model_type + '.res.yaml'

        # NOTE: We use a subroutine to generate the MITgcm configuration list

    @staticmethod
    def read_namelist(fname):
        """
        MITgcm has some additional requirements when reading namelists, so
        isolate the logic to this routine
        """

        # MITgcm strips shell-style (#) comments from its namelists
        nml_parser = f90nml.Parser()
        nml_parser.comment_tokens += '#'

        return nml_parser.read(fname)

    def setup(self):

        # TODO: Find a better place to generate this list
        files = [f for f in os.listdir(self.control_path)
                 if f.startswith('data')]
        files.append('eedata')

        # Rudimentary check that matching files are namelists. Can only check
        # if namelist is empty. May excluded false positives, but these are
        # devoid of useful information in that case
        for fname in files:
            try:
                data_nml = self.read_namelist(fname)
            except Exception as e:
                data_nml = []

            if len(data_nml) > 0:
                self.config_files.append(fname)
            else:
                print("Excluding {0} from configuration files: assumed "
                      "to be not a namelist file (or empty)".format(fname))

        # Generic model setup
        super(Mitgcm, self).setup()

        if self.prior_restart_path and not self.expt.repeat_run:
            # Determine total number of timesteps since initialisation
            core_restarts = [f for f in os.listdir(self.prior_restart_path)
                             if f.startswith('pickup.')]
            try:
                # NOTE: Use the most recent, in case of multiple restarts
                n_iter0 = max([int(f.split('.')[1]) for f in core_restarts])
            except ValueError:
                sys.exit("payu: error: no restart files found.")
        else:
            n_iter0 = 0

        # Update configuration file 'data'
        data_path = os.path.join(self.work_path, 'data')
        data_nml = self.read_namelist(data_path)

        # Timesteps are either global (deltat) or divided into momentum
        # (deltatmom) and tracer (deltat).  If deltat is missing, then we just
        # try deltatmom.  But I am not sure how to best handle this case.

        restart_calendar_path = os.path.join(self.work_init_path,
                                             self.restart_calendar_file)
        # TODO: Sort this out with an MITgcm user
        try:
            dt = float(data_nml['parm03']['deltat'])
        except KeyError:
            dt = float(data_nml['parm03']['deltatmom'])

        # Basetime defaults to zero
        basetime = 0.

        # Runtime is set either by timesteps (ntimesteps) or physical
        # time (startTime and endTime).
        t_start = data_nml['parm03'].get('starttime', None)
        t_end = data_nml['parm03'].get('endtime', None)

        n_timesteps = data_nml['parm03'].get('ntimesteps', None)

        # Support specifying just start and end times, and infer
        # n_timesteps from this, even if dt changes run length
        # remains the same
        if t_start is not None:
            if t_end is not None:
                # Standardise on starttime, ntimesteps and niter0
                del data_nml['parm03']['endtime']

                if n_timesteps is None:
                    print("Calculated n_timesteps from starttime and endtime")
                    n_timesteps = round((t_end - t_start) / dt)
            else:
                # Assume n_timesteps and dt set correctly
                pass

        if t_start is None or (self.prior_restart_path
           and not self.expt.repeat_run):
            # Look for a restart file from a previous run
            if os.path.exists(restart_calendar_path):
                with open(restart_calendar_path, 'r') as restart_file:
                    restart_info = yaml.safe_load(restart_file)
                t_start = float(restart_info['endtime'])
            else:
                # Use same logic as MITgcm and assume
                # constant dt for the whole experiment
                t_start = n_iter0 * dt

        # Check if deltat has changed
        if n_iter0 != round(t_start / dt):

            # Specify a pickup suffix using previous niter0
            data_nml['parm03']['pickupsuff'] = '{:010d}'.format(n_iter0)

            n_iter0_previous = n_iter0

            n_iter0 = round(t_start / dt)

            if n_iter0 * dt != t_start:
                # Modify basetime.
                # TODO: Change logic entirely to using
                # this conceptually much simpler approach
                basetime = t_start
                n_iter0 = 0

            if n_iter0 + n_timesteps == n_iter0_previous:
                mesg = ('payu : error: Timestep changed to {dt}. '
                        'Timestep at end identical to previous pickups: '
                        '{niter}\nThis would overwrite previous '
                        'pickups'.format(dt=dt, niter=(n_iter0 + n_timesteps)))
                sys.exit(mesg)

        t_end = t_start + dt * n_timesteps
        pchkpt_freq = t_end - t_start

        print('  base time:  {}'.format(basetime))
        print('  start time: {}'.format(t_start))
        print('  end time:   {}'.format(t_end))
        print('  niter0 :    {}'.format(n_iter0))
        print('  ntimesteps: {}'.format(n_timesteps))
        print('  dt:         {}'.format(dt))
        print('  end - start:     {}'.format(pchkpt_freq))
        print('  dt * ntimesteps: {}'.format(dt * n_timesteps))
        if pchkpt_freq != dt * n_timesteps:
            print('payu : error : time inconsistencies, '
                  'pchkptfreq ({}) != experiment length ({})'
                  ''.format(pchkpt_freq, dt * n_timesteps))
            sys.exit(1)

        data_nml['parm03']['startTime'] = t_start
        data_nml['parm03']['niter0'] = n_iter0
        data_nml['parm03']['endTime'] = t_end
        data_nml['parm03']['baseTime'] = basetime

        # NOTE: Consider permitting pchkpt_freq < dt * n_timesteps
        if t_end % pchkpt_freq != 0:
            # Terrible hack for when we change dt, the pickup frequency
            # no longer make sense, so have to set it to the total runtime
            data_nml['parm03']['pchkptfreq'] = t_end
        else:
            data_nml['parm03']['pchkptfreq'] = pchkpt_freq

        data_nml['parm03']['chkptfreq'] = 0

        data_nml.write(data_path, force=True)

        # Patch or create data.mnc
        mnc_header = os.path.join(self.work_path, 'mnc_')

        data_mnc_path = os.path.join(self.work_path, 'data.mnc')
        try:
            data_mnc_nml = self.read_namelist(data_mnc_path)
            data_mnc_nml['mnc_01']['mnc_outdir_str'] = mnc_header
            data_mnc_nml.write(data_mnc_path, force=True)

        except IOError as exc:
            if exc.errno == errno.ENOENT:

                mnc_01_grp = {
                    'mnc_use_outdir':   True,
                    'mnc_use_name_ni0': True,
                    'mnc_outdir_str':   mnc_header,
                    'mnc_outdir_date':  True,
                    'monitor_mnc':      True
                }
                data_mnc_nml = f90nml.Namelist(mnc_01=mnc_01_grp)
                data_mnc_nml.write(data_mnc_path)
            else:
                raise

    def archive(self):

        # Need to parse the data namelist file to access the
        # endTime
        data_path = os.path.join(self.work_path, 'data')
        data_nml = self.read_namelist(data_path)

        # Save model time to restart next run
        with open(os.path.join(self.restart_path,
                  self.restart_calendar_file), 'w') as restart_file:
            restart = {'endtime': data_nml['parm03']['endTime']}
            restart_file.write(yaml.dump(restart, default_flow_style=False))

        # Remove symbolic links to input or pickup files:
        for f in os.listdir(self.work_path):
            f_path = os.path.join(self.work_path, f)
            if os.path.islink(f_path):
                os.remove(f_path)

        # Move files outside of mnc_* directories
        mnc_paths = [os.path.join(self.work_path, d)
                     for d in os.listdir(self.work_path)
                     if d.startswith('mnc_')]

        for path in mnc_paths:
            for f in os.listdir(path):
                f_path = os.path.join(path, f)
                sh.move(f_path, self.work_path)
            os.rmdir(path)

        mkdir_p(self.restart_path)

        # Move pickups but don't include intermediate pickupts ('ckpt's)
        restart_files = [f for f in os.listdir(self.work_path)
                         if f.startswith('pickup') and
                         not f.split('.')[1].startswith('ckpt')]

        # Tar and compress the output files
        stdout_files = [f for f in os.listdir(self.work_path)
                        if f.startswith('STDOUT.')]

        if stdout_files:
            cmd = 'tar -C {0} -c -j -f {1}'.format(
                self.work_path,
                os.path.join(self.work_path, 'STDOUT.tar.bz2'))

            rc = sp.Popen(shlex.split(cmd) + stdout_files).wait()
            assert rc == 0

        for f in stdout_files:
            os.remove(os.path.join(self.work_path, f))

        for f in restart_files:
            f_src = os.path.join(self.work_path, f)
            sh.move(f_src, self.restart_path)

    def collate(self, clear_tiles=True, partition=None):
        from mnctools import mnctools as mnc

        # Use leading tiles to construct a tile manifest
        # Don't collate the pickup files
        # Tiled format: <field>.t###.nc
        output_fnames = [f.replace('.t001.', '.')
                         for f in os.listdir(self.output_path)
                         if f.endswith('.t001.nc') and
                         not f.startswith('pickup')]

        tile_fnames = {}
        for fname in output_fnames:
            f_header = fname.rsplit('.', 1)[0]

            tile_fnames[fname] = [os.path.join(self.output_path, f)
                                  for f in os.listdir(self.output_path)
                                  if f.startswith(f_header + '.') and
                                  f.split('.')[-2].startswith('t') and
                                  f.split('.')[-2].lstrip('t').isdigit()]

        for fname in tile_fnames:
            mnc.collate(tile_fnames[fname],
                        os.path.join(self.output_path, fname),
                        partition)

        if clear_tiles:
            for fname in tile_fnames:
                for tile_fname in tile_fnames[fname]:
                    os.remove(tile_fname)
