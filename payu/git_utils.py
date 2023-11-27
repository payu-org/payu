"""Simple wrappers around git commands

Using the GitPython library for interacting with Git
"""

import warnings
from pathlib import Path
from typing import Optional, Union, List, Dict, Set

import git
import configparser


class PayuBranchError(Exception):
    """Custom exception for payu branch operations"""


class PayuGitWarning(Warning):
    """Custom warning class - useful for testing"""


def get_git_repository(repo_path: Union[Path, str],
                       initialise: bool = False,
                       catch_error: bool = False) -> Optional[git.Repo]:
    """Return a PythonGit repository object at given path. If initialise is
    true, it will attempt to initialise a repository if it does not exist.
    Otherwise, if catch_error is true, it will return None"""
    try:
        repo = git.Repo(repo_path)
        return repo
    except git.exc.InvalidGitRepositoryError:
        if initialise:
            repo = git.Repo.init(repo_path)
            print(f"Initialised new git repository at: {repo_path}")
            return repo

        warnings.warn(
            f"Path is not a valid git repository: {repo_path}",
            PayuGitWarning
        )
        if catch_error:
            return None
        raise


def get_git_branch(repo_path: Union[Path, str]) -> Optional[str]:
    """Return the current git branch or None if repository path is not a git
    repository"""
    repo = get_git_repository(repo_path, catch_error=True)
    if repo:
        return str(repo.active_branch)


def get_git_user_info(repo_path: Union[Path, str],
                      config_key: str,
                      example_value: str) -> Optional[str]:
    """Return git config user info, None otherwise. Used for retrieving
    name and email saved in git"""
    repo = get_git_repository(repo_path, catch_error=True)
    if repo is None:
        return

    try:
        user_value = repo.config_reader().get_value('user', config_key)
        return user_value
    except (configparser.NoSectionError, configparser.NoOptionError):
        print(
            f'No git config set for user.{config_key}. '
            'To set run the following inside the control repository:\n'
            f'    git config user.{config_key} "{example_value}"'
        )


def git_commit(repo_path: Union[Path, str],
               commit_message: str,
               paths_to_commit: List[Union[Path, str]]) -> None:
    """Add a git commit of changes to paths"""
    # Get/Create git repository - initialise is true as adding a commit
    # directly after
    repo = get_git_repository(repo_path, initialise=True)

    # Un-stage any pre-existing changes
    repo.index.reset()

    # Check if paths to commit have changed, or it is an untracked file
    changes = False
    untracked_files = [Path(repo_path) / path for path in repo.untracked_files]
    for path in paths_to_commit:
        if repo.git.diff(None, path) or path in untracked_files:
            repo.index.add([path])
            changes = True

    # Run commit if there's changes
    if changes:
        repo.index.commit(commit_message)
        print(commit_message)


def local_branches_dict(repo: git.Repo) -> Dict[str, git.Head]:
    """Return a dictionary mapping local branch names to git.Head objects"""
    branch_names_dict = {}
    for head in repo.heads:
        branch_names_dict[head.name] = head
    return branch_names_dict


def remote_branches_dict(repo: git.Repo) -> Dict[str, git.Head]:
    """Return a dictionary mapping remote branch names to git.Head objects"""
    branch_names_dict = {}
    for remote in repo.remotes:
        remote.fetch()
        for ref in remote.refs:
            branch_names_dict[ref.remote_head] = ref
    return branch_names_dict


def git_checkout_branch(repo_path: Union[Path, str],
                        branch_name: str,
                        new_branch: bool = False,
                        start_point: Optional[str] = None) -> None:
    """Checkout branch and create branch if specified"""
    # Get git repository
    repo = get_git_repository(repo_path)

    # Existing branches
    local_branches = local_branches_dict(repo).keys()
    remote_branches = remote_branches_dict(repo)
    all_branches = local_branches | set(remote_branches.keys())

    # Create new branch, if specified
    if new_branch:
        if branch_name in all_branches:
            raise PayuBranchError(
                f"A branch named {branch_name} already exists. "
                "To checkout this branch, remove the new branch flag '-b' "
                "from the checkout command."
            )

        if start_point is not None:
            if (start_point not in local_branches and
                    start_point in remote_branches):
                # Use hash for remote start point -local branch names work fine
                start_point = remote_branches[start_point].commit
            branch = repo.create_head(branch_name, commit=start_point)
        else:
            branch = repo.create_head(branch_name)
        branch.checkout()

        print(f"Created and checked out new branch: {branch_name}")
        return

    # Checkout branch
    if branch_name not in all_branches:
        raise PayuBranchError(
            f"There is no existing branch called {branch_name}. "
            "To create this branch, add the new branch flag '-b' "
            "to the checkout command."
        )

    repo.git.checkout(branch_name)
    print(f"Checked out branch: {branch_name}")


def git_clone(repository: str,
              directory: Union[str, Path],
              branch: Optional[str] = None) -> None:
    """Clone repository to directory"""
    # Clone the repository
    if branch is not None:
        git.Repo.clone_from(repository,
                            to_path=directory,
                            branch=branch)
    else:
        git.Repo.clone_from(repository, to_path=directory)

    print(f"Cloned repository from {repository} to directory: {directory}")
