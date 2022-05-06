"""Module to handle argparse in a multi-level inheritance system of objects
"""

import argparse

from bigmultipipe import OUTNAME_APPEND

class ArgparseHandler:
    def __init__(self, parser):
        self.parser = parser

    def add_all(self):
        pass

class BMPArgparseMixin:
    """Adds basic `argparse` options relevant to `~bigmultipipe.BigMultiPipe`.  See `bigmultipipe.argparsehandler`"""

    outname_append = OUTNAME_APPEND

    def add_outdir(self, 
                   default='.',
                   help='Directory to which files will be written',
                   **kwargs):
        """Add outdir parameter to `argparse.ArgumentSelf.Parser`

        Parameters
        ----------
        default : str
            Default outdir
            Default is `.`

        help : str
            Description
            Default is 'Directory to which files will be written'
        """
        option = 'outdir'
        self.parser.add_argument('--' + option,
                            default=default, help=help, **kwargs)
        
    def add_create_outdir(self, 
                          default=False,
                          help=None,
                          **kwargs):
        option = 'create_outdir'
        if help is None:
            help = (f'Create outdir')
        self.parser.add_argument('--' + option,
                                 action=argparse.BooleanOptionalAction,
                                 default=default,
                                 help=help, **kwargs)

    def add_read_pout(self, 
                      default=False,
                      help=None,
                      **kwargs):
        option = 'read_pout'
        if help is None:
            help = (f'Read pout pickle file')
        self.parser.add_argument('--' + option,
                                 action=argparse.BooleanOptionalAction,
                                 default=default,
                                 help=help, **kwargs)

    def add_write_pout(self, 
                      default=False,
                      help=None,
                      **kwargs):
        option = 'write_pout'
        if help is None:
            help = (f'Write pout pickle file')
        self.parser.add_argument('--' + option,
                                 action=argparse.BooleanOptionalAction,
                                 default=default,
                                 help=help, **kwargs)

    def add_outname_append(self, 
                           default=None,
                           help=None,
                           **kwargs):
        default = default or self.outname_append
        option = 'outname_append'
        if help is None:
            help = (f'string to append to output files to prevent '
                    f'overwrite (default: {default})')
        self.parser.add_argument('--' + option, default=default,
                                 help=help, **kwargs)

    def add_num_processes(self, 
                          default=0.8,
                          help=None,
                          **kwargs):
        option = 'num_processes'
        if help is None:
            help = (f'number of subprocesses for parallelization; '
                    f'0=all cores, <1 = fraction of total cores; '
                    f'(default={default})')
        self.parser.add_argument('--' + option, type=float,
                                 default=default, help=help, **kwargs)
        
    def add_mem_available(self, 
                          default=None,
                          help=None,
                          **kwargs):
        option = 'mem_available'
        if help is None:
            help = 'hard-coded available memory'
        self.parser.add_argument('--' + option, type=float,
                                 default=default, help=help, **kwargs)

    def add_mem_frac(self, 
                     default=0.8,
                     help=None,
                     **kwargs):
        option = 'mem_frac'
        if help is None:
            help = ('maximum fraction of memory to be used; '
                    f'(default={default})')
        self.parser.add_argument('--' + option, type=float,
                                 default=default, help=help, **kwargs)

    def add_process_size(self, 
                         default=0.8,
                         help=None,
                         **kwargs):
        option = 'process_size'
        if help is None:
            help = 'process size in bytes'
        self.parser.add_argument('--' + option, type=float,
                                 default=default, help=help, **kwargs)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='argparse_handler sample code')
    aph = ArgparseHandler(parser)
    aph.add_all()
    args = parser.parse_args()
    aph.cmd(args)
