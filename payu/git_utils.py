"""Simple wrappers around git commands

Using the GitPython library for interacting with Git
"""

import warnings
from pathlib import Path
from typing import Optional, Union, List, Dict

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


class GitRepository:
    """Simple wrapper around git python's repo and methods"""

    def __init__(self,
                 repo_path: Union[Path, str],
                 repo: Optional[git.Repo] = None,
                 catch_error: bool = False):
        self.repo_path = repo_path

        # Initialise git repository object
        if repo is None:
            repo = get_git_repository(repo_path, catch_error=catch_error)
        self.repo = repo

    def get_branch_name(self) -> Optional[str]:
        """Return the current git branch or None if repository path is
        not a git repository"""
        if self.repo:
            return str(self.repo.active_branch)

    def get_hash(self) -> Optional[str]:
        """Return the current git commit hash or None if repository path is
          not a git repository"""
        if self.repo:
            return self.repo.active_branch.object.hexsha

    def get_origin_url(self) -> Optional[str]:
        """Return url of remote origin if it exists"""
        if self.repo and self.repo.remotes and self.repo.remotes.origin:
            return self.repo.remotes.origin.url

    def get_user_info(self, config_key: str) -> Optional[str]:
        """Return git config user info, None otherwise. Used for retrieving
        name and email saved in git"""
        if self.repo is None:
            return

        try:
            config_reader = self.repo.config_reader()
            return config_reader.get_value('user', config_key)
        except (configparser.NoSectionError, configparser.NoOptionError):
            # No git config set for user.$config_key
            return

    def commit(self,
               commit_message: str,
               paths_to_commit: List[Union[Path, str]]) -> None:
        """Add a git commit of changes to paths"""
        if self.repo is None:
            return

        # Un-stage any pre-existing changes
        self.repo.index.reset()

        # Check if paths to commit have changed, or it is an untracked file
        changes = False
        untracked_files = [Path(self.repo_path) / path
                           for path in self.repo.untracked_files]
        for path in paths_to_commit:
            if self.repo.git.diff(None, path) or path in untracked_files:
                self.repo.index.add([path])
                changes = True

        # Run commit if there's changes
        if changes:
            self.repo.index.commit(commit_message)
            print(commit_message)

    def local_branches_dict(self) -> Dict[str, git.Head]:
        """Return a dictionary mapping local branch names to git.Head
        objects"""
        branch_names_dict = {}
        for head in self.repo.heads:
            branch_names_dict[head.name] = head
        return branch_names_dict

    def remote_branches_dict(self) -> Dict[str, git.Head]:
        """Return a dictionary mapping remote branch names to git.Head
        objects"""
        branch_names_dict = {}
        for remote in self.repo.remotes:
            remote.fetch()
            for ref in remote.refs:
                branch_names_dict[ref.remote_head] = ref
        return branch_names_dict

    def checkout_branch(self,
                        branch_name: str,
                        new_branch: bool = False,
                        start_point: Optional[str] = None) -> None:
        """Checkout branch and create branch if specified"""
        # First check for staged changes
        if self.repo.is_dirty(index=True, working_tree=False):
            raise PayuBranchError(
                "There are staged git changes. Please stash or commit them "
                "before running the checkout command again.\n"
                "To see what files are staged, run: git status"
            )

        # Existing branches
        local_branches = self.local_branches_dict().keys()
        remote_branches = self.remote_branches_dict()
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
                    # Use hash for remote start point
                    start_point = remote_branches[start_point].commit
                branch = self.repo.create_head(branch_name, commit=start_point)
            else:
                branch = self.repo.create_head(branch_name)
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

        self.repo.git.checkout(branch_name)
        print(f"Checked out branch: {branch_name}")


def git_clone(repository: str,
              directory: Union[str, Path],
              branch: Optional[str] = None) -> GitRepository:
    """Clone repository to directory"""
    # Clone the repository
    if branch is not None:
        repo = git.Repo.clone_from(repository,
                                   to_path=directory,
                                   branch=branch)
    else:
        repo = git.Repo.clone_from(repository, to_path=directory)

    print(f"Cloned repository from {repository} to directory: {directory}")

    return GitRepository(repo_path=directory, repo=repo)
