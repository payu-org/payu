'''Custom Payu Exceptions. For catching user errors.
 - Use them when user inputs are not recognised. 
 - They intend to provide a polite, actionable message to users.

Standard Exceptions (ex. ValueError, TypeError) are for the Developer.
 - Use them to catch exceptions from another piece of code or 
   function calls.
 - We want the program to crash with a stack trace so developer 
   could fix the bug.
'''

class PayuError(Exception):
    '''
    Base class for all Payu Exceptions. 
    Any error that inherits from this class - represents an expected failure 
    mode (ex. bad user input, missing files) rather than a code bug.
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


class PayuBranchError(PayuError):
    '''
    Raised when there are issues with Git branches.
    '''
    exit_code = 4


class PayuRunError(PayuError):
    '''
    Raised when an active model run fails unexpectedly.
    '''
    exit_code = 5
