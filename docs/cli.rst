.. _floq-client:
    https://github.com/google/floq-client/blob/main/scripts/cli.py

CLI script
----------

Both jobs queue and TPU worker can be controlled manually using `floq-client`_
CLI script. Simply provide API key as the input argument and the resource
command.

::

    # Display help
    $ floq-client --help

    # Jobs queue commands
    $ floq-client my_api_key jobs {display,flush}

    # TPU worker commands
    $ floq-client my_api_key worker {start,stop,restart,status}