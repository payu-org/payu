"""nml
Parse fortran namelist files into dicts of standard Python data types.
Contact: Marshall Ward <nml@marshallward.org>
"""

import shlex

f90quotes = ["'", '"']

def parse(nml_fname):

    f = open(nml_fname, 'r')

    f90 = shlex.shlex(f)
    f90.commenters = '!'
    f90.wordchars += '.-()'   # Numerical characters
    tokens = iter(f90)

    nmls = {}

    for t in tokens:

        # Find the next group header token
        while t != '&':
            t = tokens.next()

        # Read group name following '&'
        t = tokens.next()

        nml_grp = t
        nml_grp_vars = {}

        current_var_name = None
        current_var_vals = []

        # Current token is group name prior to loop
        while t != '/':

            prior_t = t
            t = tokens.next()

            if current_var_name and not t == '=':
                if (prior_t, t) == (',', ','):
                    current_var_vals.append(None)
                elif prior_t != ',':
                    try:
                        f90val = f90type(prior_t)
                    except ValueError:
                        print(current_var_name, prior_t)
                    current_var_vals.append(f90val)

            # Finalize the current variable
            if current_var_name and (t == '=' or t == '/'):

                if len(current_var_vals) == 1:
                    current_var_vals = current_var_vals[0]
                nml_grp_vars[current_var_name] = current_var_vals

                # XXX: Needed?
                current_var_name = None
                current_var_vals = []

            # Activate the next variable
            if t == '=':
                current_var_name = prior_t
                t = tokens.next()

            # Append to namelist
            if t == '/':
                nmls[nml_grp] = nml_grp_vars

    f.close()

    return nmls


#---
def f90type(s):
    """Convert string repr of Fortran type to equivalent Python type."""

    recast_funcs = [int, float, f90complex, f90bool, f90str]

    for f90type in recast_funcs:
        try:
            v = f90type(s)
            return v
        except ValueError:
            continue

    # If all test failed, then raise ValueError
    raise ValueError


#---
def f90complex(s):
    assert type(s) == str

    if s[0] == '(' and s[-1] == ')' and len(s,split(',') == 2):
        s_re, s_im = s[1:-1].split(',', 1)
 
        # NOTE: Failed float(str) will raise ValueError
        return complex(float(s_re), float(s_im))
    else:
        raise ValueError('{} must be in complex number form (x,y)'.format(s))


#---
def f90bool(s):
    assert type(s) == str

    # TODO: Only one '.' should be permitted (p = \.?[tTfT])
    ss = s.lower().strip('.')
    if ss.startswith('t'):
        return True
    elif ss.startswith('f'):
        return False
    else:
        raise ValueError('{} is not a valid logical constant.'.format(s))


#---
def f90str(s):
    assert type(s) == str

    if s[0] in f90quotes and s[-1] in f90quotes:
        return s[1:-1]

    raise ValueError
