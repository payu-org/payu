'''Custom Payu Exceptions for handling user-facing errors.
 - Use these when user input is invalid or not recognised. 
 - They intend to provide a polite, actionable message to users.

---

Note: 
Standard Exceptions (e.g. ValueError, TypeError) are intended for
developer-facing errors. Use them when catching issues from internal
code or function calls.
'''

class PayuError(Exception):
    '''
    Base class for all Payu Exceptions. 
    Any error that inherits from this class - represents an expected failure 
    mode (e.g. bad user input, missing files) rather than a code bug.
    '''
    exit_code = 1


class PayuConfigError(PayuError):
    '''
    Raised when there is an error reading the config.yaml file.
    '''
    exit_code = 2


class PayuFileNotFoundError(PayuError):
    '''
    Raised when a required file or directory for a model is missing.
    '''
    exit_code = 3


class PayuRunError(PayuError):
    '''
    Raised when an active model run fails unexpectedly.
    '''
    exit_code = 4


class PayuGitError(PayuError):
    '''
    Raised when there are Git related issues .
    '''
    exit_code = 5


class PayuBranchError(PayuError):
    '''
    Custom exception for payu branch operations
    '''
    exit_code = 6
 