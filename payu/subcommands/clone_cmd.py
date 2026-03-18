"""Run the `payu clone` command.

:copyright: Copyright 2018 Marshall Ward, see AUTHORS for details.
:license: Apache License, Version 2.0, see LICENSE for details.
"""

from argparse import RawDescriptionHelpFormatter
from pathlib import Path
import tempfile
import questionary
import subprocess
import os
import sys
try:
    from prompt_toolkit.completion import PathCompleter
    has_completer = True
except ImportError:
    has_completer = False

from payu.branch import clone
import payu.subcommands.args as args

accessible_style = questionary.Style([
    ('question', 'bold'),               
    ('answer', 'fg:#ff9800 bold'),
    ('selected', 'fg:#ff9800'),
])

def qprint(message):
    """Helper function to print messages in a consistent style."""
    questionary.print(message, style="bold italic fg:yellow")

def print_error_missing_args():
    """Print an error message when required arguments are missing."""
    print("Error: Repository URL and local directory must be provided for cloning.")
    print("If you want to provide arguments interactively, please run")
    print("    `payu clone <repo> <local_directory> -I`")
    print("or")
    print("    `payu clone <repo> -I`")
    print("or simply run")
    print("    `payu clone`")

def print_restart_number_message():
    print(
           f"To continue the sequence from your restart files, please run \n    `payu run -i <N>`\nfor your first run after cloning, where <N> is the new index."
    )

title = 'clone'
parameters = {
    'description': (
        'A wrapper around git clone. Clones a control repository and setup '
        'new experiment metadata'
    ),
    'epilog': (
        'Example usage:\n'
        '\n  To clone repository and checkout an existing git branch:\n'
        '    payu clone -B <branch_name> <repository> <local_directory>\n'
        '\n  To clone and create a new branch from an existing branch:\n'
        '    payu clone -B <branch_name> -b <new_branch_name> <repository> <local_directory>\n'
        '\n  To clone and create a new branch from an existing commit or tag:\n'
        '    payu clone -s <commit_or_tag> -b <new_branch_name> <repository> <local_directory>\n'
        '\n  To clone and checkout a new branch, and specify a restart path to start from:\n'
        '    payu clone -b <new_branch_name> -r <path_to_restart_dir> <repository> <local_directory>\n'
    ),
    'formatter_class': RawDescriptionHelpFormatter,
}

arguments = [args.model, args.config, args.laboratory,
             args.keep_uuid, args.clone_branch,
             args.repository, args.local_directory,
             args.new_branch_name, args.restart_path,
             args.parent_experiment, args.clone_start_point,
             args.prompt_user]


def transform_strings_to_path(path_str=None):
    return Path(path_str) if path_str is not None else None


def runcmd(model_type, config_path, lab_path, keep_uuid,
           branch, repository, local_directory, new_branch_name, restart_path,
           parent_experiment, start_point, prompt_user):
    """Execute the command."""
    if prompt_user or (repository is None and local_directory is None):
        qprint("Welcome to the Payu Clone Wizard!")
        qprint("Press 'Ctrl+C' at any time to exit.")
        user_params = prompts_for_clone(repository, local_directory, branch, start_point)
        repository = user_params.get('repository')
        local_directory = user_params.get('local_directory')
        branch = user_params.get('branch')
        start_point = user_params.get('start_point')
        keep_uuid = user_params.get('keep_uuid')
        new_branch_name = user_params.get('new_branch_name')
        restart_path = user_params.get('restart_path')

    if repository is None or local_directory is None:
        print_error_missing_args()
        sys.exit(1)

    config_path = transform_strings_to_path(config_path)
    restart_path = transform_strings_to_path(restart_path)
    lab_path = transform_strings_to_path(lab_path)
    directory = transform_strings_to_path(local_directory)

    clone(repository=repository,
          directory=directory,
          branch=branch,
          keep_uuid=keep_uuid,
          model_type=model_type,
          config_path=config_path,
          lab_path=lab_path,
          new_branch_name=new_branch_name,
          restart_path=restart_path,
          parent_experiment=parent_experiment,
          start_point=start_point)


runscript = runcmd

def prompts_for_clone(repository, local_directory, branch, start_point):
    """Prompt the user for input to guide the cloning process."""
    # Source selection
    if repository is None:
        repository = ask_for_repo_url()
    else:
        qprint(f"Cloning from repository: {repository}")
    if branch is None and start_point is None:
        branch_or_tag = select_branch_or_tag()
        if branch_or_tag == "An existing branch":
            branches = fetch_branches(repository)
            branch = ask_for_branch_name(branches)
        else:
            qprint("You chose to clone from a tag or commit.")
            qprint("Payu will create a new experiment UUID and new branch for this clone.")
            all_tags = fetch_tags(repository)
            start_point = ask_for_tag_or_commit(all_tags)

    elif branch is not None:
        qprint(f"Cloning from branch: {branch}")
    elif start_point is not None:
        qprint(f"Cloning from tag/commit: {start_point}")

    # Local directory and experiment setup
    if local_directory is None:
        local_directory = ask_for_local_directory()
    else:
        qprint(f"Cloning into local directory: {local_directory}")
    if branch is not None:
        is_new_expt = confirm_new_experiment()
    else:
        is_new_expt = True

    # New branch name and restart path (if applicable)
    if is_new_expt:
        new_branch_name = ask_for_new_branch_name()
        if confirm_restart_path():
            restart_path = ask_for_restart_path()
        else:
            restart_path = None
    else:
        qprint(
            "Payu clone will keep the same branch name and UUID as the original experiment."
        )
        restart_path = ask_for_restart_path()
        print_restart_number_message()

    return {
        'repository': repository,
        'branch': branch,
        'start_point': start_point,
        'local_directory': local_directory,
        'new_branch_name': new_branch_name if is_new_expt else None,
        'restart_path': restart_path,
        'keep_uuid': not is_new_expt
    }

def fetch_branches(url):
    """Fetch all branches from the remote repository."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--heads", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        branches = [line.split('\t')[1].replace("refs/heads/", "") for line in result.stdout.splitlines()]
        return branches
    except subprocess.CalledProcessError as e:
        print(f"Error fetching branches: {e}")
        sys.exit(1)

def fetch_tags(url):
    """Fetch all tags from the remote repository."""
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--tags", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        tags = [line.split('\t')[1].replace("refs/tags/", "") for line in result.stdout.splitlines()]
        return tags
    except subprocess.CalledProcessError as e:
        print(f"Error fetching tags: {e}")
        sys.exit(1)

def safe_ask(question_obj):
    """ A helper function to safely ask a question and handle KeyboardInterrupt. """
    answer = question_obj.ask()
    if answer is None:
        print("Clone process cancelled by user. Exiting.")
        sys.exit(0)
    return answer

def ask_for_repo_url():
    """Ask the user for the repository URL they want to clone."""
    return safe_ask(questionary.text(
        "Please enter the URL of the repository, or the local path of a configuration you want to clone:",
        instruction="(e.g., https://github.com/payu-org/bowl1.git, or /path/to/local/experiment)",
        validate=lambda text: True if text else "Repository URL cannot be empty."
    ))

def select_branch_or_tag():
    """Ask the user if they want to clone based on an existing branch or a tag/commit."""
    return safe_ask(questionary.select(
        "Do you want to clone the repo based on:",
        choices=[
            "An existing branch",
            "A tag or a commit",
        ]))

def ask_for_branch_name(branches):
    """Ask the user for the name of the branch they want to clone."""
    return safe_ask(questionary.autocomplete(
        "Please enter the name of the branch you want to clone ('Tab' to browse all branches):",
        choices=branches,
        validate=lambda text: True if text in branches
                                else "Branch name is not valid.",
        style=accessible_style
    ))

def ask_for_tag_or_commit(all_tags):
    """Ask the user for the name of the tag or commit hash they want to clone."""
    return safe_ask(questionary.autocomplete(
        "Please enter the name of the tag or the commit hash you want to clone from ('Tab' to browse all tags):",
        choices=all_tags,
        validate=lambda text: True if text else "Tag or commit cannot be empty.",
        style=accessible_style
    ))

def validate_local_directory(path_str):
    """Validate the local directory path provided by the user."""
    if not path_str:
        return "Directory name cannot be empty."

    dir_path = transform_strings_to_path(path_str)
    if dir_path.exists() and any(dir_path.iterdir()):
        return (f"The directory '{dir_path}' already exists and is not empty.\nPlease choose a different directory.")
    return True

def ask_for_local_directory():
    """Ask the user for the name of the local directory they want to create."""
    # check if path is empty
    return safe_ask(questionary.text(
        "How would you like to name your local experiment directory?",
        validate=validate_local_directory
    ))

def confirm_new_experiment():
    """Ask the user if this is a new experiment"""
    return safe_ask(questionary.confirm(
        "Is this a new experiment? (If yes, payu will create a new branch.)"
    ))

def ask_for_new_branch_name():
    """Ask the user for the name of the new branch they want to create."""
    return safe_ask(questionary.text(
            "Please enter the name of the new branch you want to create:",
            validate=lambda text: True if text else "Branch name cannot be empty."
        ))

def confirm_restart_path():
    """Ask the user if they want to specify a restart path to start from."""
    return safe_ask(questionary.confirm(
            "Are you starting from an existing restart path?"
        ))

def validate_restart_path(path_str):
    """Validate the restart path exists and is not empty."""
    if not path_str:
        return "Restart path cannot be empty."
    
    dir_path = transform_strings_to_path(path_str)
    if dir_path.exists() and any(dir_path.iterdir()):
        return True
    else:
        return "Restart path does not exist or is empty. Please enter a valid path."

def ask_for_restart_path():
    """Ask the user for the path to the restart directory they want to use."""
    path_completer = PathCompleter(only_directories=True, expanduser=True) if has_completer else None
    instruction = " ('Tab' to browse, '/' to enter folder):" if has_completer else ":"
    return safe_ask(questionary.text(
                "Please enter the restart path you want to use" + instruction,
                validate=validate_restart_path,
                completer=path_completer
            ))