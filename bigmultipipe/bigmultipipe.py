"""Provides tools for parallel pipeline processing of large data structures"""

import os
import multiprocessing
# For NoDaemonPool we must import this explicitly, it is not
# imported by the top-level multiprocessing module.
import multiprocessing.pool

import psutil

# Adapted from various source on the web
# https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
class NoDaemonProcess(multiprocessing.Process):
    """Make ``daemon`` attribute always return False, thus enabling
    child processes to run their own sub-processes"""
    def _get_daemon(self):
        """Always returns `False`"""
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NoDaemonPool(multiprocessing.pool.Pool):
    """Works with :class:`NoDaemonProcess` to allows child processes to run their own sub-processes"""
    Process = NoDaemonProcess

class WorkerWithKwargs():
    """
    Class to hold static kwargs for use with, e.g., :meth:`multiprocessing.pool.Pool.map()` 

    Parameters
    ----------
    function : function
        Function called by :meth:`~WorkerWithKwargs.worker()` 

    kwargs : kwargs
        kwargs to be passed to function

    Attributes
    ----------
    function : function
        Function called by :meth:`~WorkerWithKwargs.worker()` 

    kwargs : kwargs
        kwargs to be passed to function

    Examples
    --------
    This code::
    
        >>> def add_mult(a, to_add=0, to_mult=1):
        >>>     return (a + to_add) * to_mult
        >>> 
        >>> wwk = WorkerWithKwargs(add_mult, to_add=3, to_mult=10)
        >>> print(wwk.worker(3))
        >>> print(wwk.worker(3)) # doctest: +FLOAT_CMP
        60

    is equivalent to::

        >>> print(add_mult(3, to_add=3, to_mult=10))
        >>> w3 = add_mult(3, to_add=3, to_mult=10)
        >>> w3 # doctest: +FLOAT_CMP
        60

    """
    def __init__(self,
                 function,
                 **kwargs):
        self.function = function
        self.kwargs = kwargs
    def worker(self, *args):
        """Method called to execute function with saved ``**kwargs``

        Parameters
        ----------
        \*args : any type

        Returns
        -------
        function(\*args, \*\*kwargs)

        """

        return self.function(*args, **self.kwargs)

def num_can_process(num_to_process=None,
                    num_processes=None,
                    mem_available=None,
                    mem_frac=0.8,
                    process_size=None,
                    error_if_zero=True):
    """
    Calculates maximum number of processes that can run simultaneously

    Parameters
    ----------

    num_to_process : int or ``None``, optional
        Total number of items to process.  This number is returned if
        it is less than the maximum possible simultaneous processes.
        If ``None``, not used in calculation.
        Default is ``None``

    num_processes : int or ``None``, optional
        Maximum number of parallel processes.  If ``None``, set to the
        number of physical (not logical) cores available using
        :func:`psutil.cpu_count(logical=False) <psutil.cpu_count>`
        Default is ``None``

    mem_available : int or None. optional
        Amount of memory available in bytes for the total set of 
        processes.  If ``None``, ``mem_frac`` parameter is used.
        Default is ``None``

    mem_frac : float, optional
        Maximum fraction of current memory available that total set of 
        processes is allowed to occupy.  Current memory available is
        queried
        Default is ``0.8``

    process_size : int, or None, optional
        Maximum process size in bytes of an individual process.  If
        None, processes are assumed to be small enough to all fit in
        memory at once.
        Default is ``None``

    error_if_zero : bool, optional
        If True, throw an :class:`EnvironmentError` error if return
        value would be zero.  Useful for catching case when there is
        not enough memory for even one process.
        Default is ``True``

    """
    if num_processes is None:
        num_processes = psutil.cpu_count(logical=False)
    if num_to_process is None:
        num_to_process = num_processes
    if mem_available is not None:
        max_mem = mem_available
    else:
        mem = psutil.virtual_memory()
        max_mem = mem.available*mem_frac
    if process_size is None:
        max_n = num_processes
    else:
        max_n = int(max_mem / process_size)
    if error_if_zero and max_n == 0:
        raise EnvironmentError(f'Current memory {max_mem/2**20} MiB insufficient for process size {process_size/2**20} MiB')

    return min(num_to_process, num_processes, max_n)

class BigMultiPipe():
    """Base class for memory- and processing power-optimized pipelines

    Parameters
    ----------
    num_processes, mem_available, mem_frac, process_size : optional
        These parameters tune computer processing and memory resources
        and are used when the :meth:`pipeline` method is executed.
        See documentation for :func:`num_can_process` for use, noting
        that the ``num_to_process`` argument of that function is
        set to the number of input filenames in :meth:`pipeline`

    outdir : str, None, optional
    	Name of directory into which output files will be written.  If
    	None, current directory in which the Python process is running
    	will be used.
        Default is ``None``

    create_outdir : bool, optional
        If True, create outdir and any needed parent directories.
        Does not raise an error if outdir already exists.
        Default is ``False``

    outname_append : str, optional
        String to append to outname to avoid risk of input file
        overwrite.  Example input file ``test.dat`` would become
        output file ``test_bmp.dat``
        Default is ``_bmp``

    pre_process_list : list

        List of functions called by :func:`pre_process` before primary
        processing step.  Intended to implement filtering and control
        features as described in :ref:`Discussion of Design <design>`.
        Each function must accept one positional parameter, ``data``,
        keyword arguments necessary for its internal functioning, and
        ``**kwargs`` to ignore keyword parameters not processed by the
        function.  The return value of each function must be a
        `tuple`, of the form ``(data, additional_keywords)`` where
        ``additional_keywords`` is of type `dict`.  If ``data`` is
        returned as ``None``, processing of that file stops, no output
        file is written, and ``None`` is returned instead of an output
        filename.  Below are examples.  See :ref:`Example` to see this
        code in use in a functioning pipeline.

        >>> def reject(data, reject_value=None, **kwargs):
        >>>     if reject_value is None:
        >>>         return (data, {})
        >>>     if data[0,0] == reject_value:
        >>>         # --> Return data=None to reject data
        >>>         return (None, {})
        >>>     return (data, {})
        >>> 
        >>> def boost_later(data, boost_target=None, boost_amount=None, **kwargs):
        >>>     if boost_target is None or boost_amount is None:
        >>>         return (data, {})
        >>>     if data[0,0] == boost_target:
        >>>         # --> This is equivalent to setting a keyword parameter
        >>>         # need_to_boost_by=boost_amount
        >>>         return (data, {'need_to_boost_by': boost_amount})
        >>>     return (data, {})

    post_process_list : list

        List of functions called by :func:`post_process` after
        primary processing step.  Indended to enable additional
        processing steps and produce metadata as discussed in
        :ref:`Discussion of Design <design>`.  Each function must
        accept two positional parameters, ``data`` and ``meta`` and
        any optional kwargs.  ``Meta`` will be of type `dict`.  The
        return value of each function must be a `tuple` in the form
        ``(data, additional_meta)``, where ``additional_metadata``
        must be of type `dict.` Because ``meta`` is of type `dict`, it
        can be modified directly in the function.  In this case, the
        user can return either {} or ``meta`` as ``additional_meta``,
        since the calling routine, :meth:`post_process`. uses
        :meth:`dict.update` to merge ``additional_metadata`` into
        ``meta``.  Below are examples.  See :ref:`Example` for an
        example of how to use them in a functioning pipeline.

        >>> def later_booster(data, meta, need_to_boost_by=None, **kwargs):
        >>>     if need_to_boost_by is None:
        >>>         return (data, {})
        >>>     data = data + need_to_boost_by
        >>>     return (data, {})
        >>> 
        >>> def average(data, meta, **kwargs):
        >>>     av = np.average(data)
        >>>     return (data, {'average': av})


    PoolClass : class name or None, optional

        Typcally a subclass of :class:`multiprocessing.pool.Pool`. The
        :meth:`~multiprocessing.pool.Pool.map()` method of this class
        implements the multiprocessing feature of this module.  If
        ``None``, :class:`multiprocessing.pool.Pool` is used.  Default is
        ``None.``

    kwargs : dict, optional
        Python's kwargs construct stores additional keyword
        arguments as a dict.  In order to implement the control stream
        discussed in the introduction to this module, this dict is
        captured as property.  When any methods are run, the kwargs
        from the property are copied to a new dict object and combined
        with the kwargs passed to the method using :meth:`dict.update()`.
        This allows the parameters passed to the methods at runtime to
        override the parameters passed to the object at instantiation
        time.  This also provides a mechanism for any function in the
        system to modify the kwargs dict for flexible per-file control
        of the pipeline.

    Notes
    -----

    All parameters passed at object instantiation are stored as
    property and used to initialize the identical list of parameters
    to the :func:`BigMultiPipe.pipeline` method.  Any of these
    parameters can be overridden when that method is called by using
    the corresponding keyword (e.g., ``mem_frac=0.2``,
    ``pre_process_list=[reject_bad_file]``, etc.).  This enables
    definition of a default pipeline configuration when the object is
    instantiated that can be modified at run-time.

    """
    def __init__(self,
                 num_processes=None,
                 mem_available=None,
                 mem_frac=0.8,
                 process_size=None,
                 outdir=None,
                 create_outdir=False,
                 outname_append='_bmp',
                 pre_process_list=None,
                 post_process_list=None,
                 PoolClass=None,
                 **kwargs):
        self.num_processes = num_processes
        self.mem_available = mem_available
        self.mem_frac = mem_frac
        self.process_size = process_size
        if pre_process_list is None:
            pre_process_list = []
        if post_process_list is None:
            post_process_list = []
        self.pre_process_list = pre_process_list
        self.post_process_list = post_process_list
        if PoolClass is None:
            PoolClass = multiprocessing.Pool
        self.PoolClass = PoolClass
        self.outdir = outdir
        self.create_outdir = create_outdir
        self.outname_append = outname_append
        self.kwargs = kwargs

    def kwargs_merge(self, **kwargs):
        """Merge \*\*kwargs with \*\*kwargs provided on instantiation

        Intended to be called by methods

        Parameters
        ----------
        \*\*kwargs : keyword arguments
        """

        nkwargs = self.kwargs.copy()
        nkwargs.update(kwargs)
        return nkwargs
        
    def pipeline(self, in_names,
                 num_processes=None,
                 mem_available=None,
                 mem_frac=None,
                 process_size=None,
                 PoolClass=None,
                 **kwargs):
        """Runs pipeline, maximizing processing and memory resources

        Parameters
        ----------
        in_names : `list` of `str`
            List of input filenames.  Each file is processed using
            :func:`file_process`

        All other parameters : see Parameters to :class:`BigMultiPipe`

        Returns
        -------

        pout : `list` of tuples ``(outname, meta)``, one `tuple` for each
            ``in_name``.  ``Outname`` is `str` or ``None``.  If `str`,
            it is the name of the file to which the processed data
            were written.  If ``None``, the convenience function
            :func:`prune_pout` can be used to remove this tuple from
            ``pout`` and the corresponding in_name from the in_names list.
            ``Meta`` is a `dict` containing output.

        """
        if num_processes is None:
            num_processes = self.num_processes
        if mem_available is None:
            mem_available = self.mem_available
        if mem_frac is None:
            mem_frac = self.mem_frac
        if process_size is None:
            process_size = self.process_size
        if PoolClass is None:
            PoolClass = self.PoolClass
        kwargs = self.kwargs_merge(**kwargs)
        ncp = num_can_process(len(in_names),
                              num_processes=num_processes,
                              mem_available=mem_available,
                              mem_frac=mem_frac,
                              process_size=process_size)
        wwk = WorkerWithKwargs(self.file_process, **kwargs)
        if ncp == 1:
            retvals = [wwk.worker(i) for i in in_names]
            return retvals
        with PoolClass(processes=ncp) as p:
            retvals = p.map(wwk.worker, in_names)
        return retvals
        
    def file_process(self, in_name, **kwargs):
        """Process one file in the `bigmultipipe` system

        This method can be overridden to interface with applications
        where the primary processing routine already reads the input
        data from disk and writes the output data to disk,

        Parameters
        ----------
        in_name: str
            Name of file to process.  Data from the file will be read
            by :func:`file_read` and processed by
            :func:`data_process_meta_create`.  Output filename will be
            created by :func:`outname_create` and data will be written by
            :func:`file_write`

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        (outname, meta) : tuple
            Outname is the name of file to which processed data was
            written.  Meta is the dictionary element of the tuple
            returned by :func:`data_process_meta_create`

        """
        kwargs = self.kwargs_merge(**kwargs)
        data = self.file_read(in_name, **kwargs)
        if data is None:
            return (None, {})
        data, meta = \
            self.data_process_meta_create(data, in_name=in_name, **kwargs)
        if data is None:
            return (None, meta)
        outname = self.outname_create(in_name, data, meta, **kwargs)
        outname = self.file_write(data, outname, **kwargs)
        return (outname, meta)

    def file_read(self, in_name, **kwargs):
        """Reads data file from disk.  Intended to be overridden by subclass

        Parameters
        ----------
        in_name : str
            Name of file to read

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        data : any type
            Data to be processed

        """
        
        kwargs = self.kwargs_merge(**kwargs)
        with open(in_name, 'rb') as f:
            data = f.read()
        return data

    def file_write(self, data, outname, **kwargs):
        """Write data to disk file.  Intended to be overridden by subclass

        Parameters
        ----------
        data : any type
            Processed data

        outname : str
            Name of file to write

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        outname : str
            Name of file written

        """
        kwargs = self.kwargs_merge(**kwargs)
        with open(outname, 'wb') as f:
            f.write(data)
        return outname

    def data_process_meta_create(self, data, **kwargs):
        """Process data and create metadata

        Parameters
        ----------
        data : any type
            Data to be processed by :func:`pre_process`,
            :func:`data_process`, and :func:`post_process`

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        (data, meta) : tuple
            Data is the processed data.  Meta is created by
            :func:`post_process`

        """
        kwargs = self.kwargs_merge(**kwargs)
        (data, kwargs) = self.pre_process(data, **kwargs)
        if data is None:
            return(None, {})
        data = self.data_process(data, **kwargs)
        data, meta = self.post_process(data, **kwargs)
        if data is None:
            return(None, {})
        return (data, meta)

    def pre_process(self, data,
                    pre_process_list=None,
                    **kwargs):
        """Conduct pre-processing tasks

        This method can be overridden to permanently insert
        pre-processing tasks in the pipeline for each instantiated
        object and/or the pre_process_list feature can be used for a
        more dynamic approach to inserting pre-processing tasks at
        object instantiation and/or when the pipeline is run

        Parameters
        ----------
        data : any type
            Data to be processed by the functions in pre_process_list

        pre_process_list : list
            See documentation for this parameter in Parameters section
            of :class:`BigMultiPipe`

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        (data, kwargs) : tuple
            Data are the pre-processed data.  Kwargs are the combined
            kwarg outputs from all of the pre_process_list functions.

        """
        kwargs = self.kwargs_merge(**kwargs)
        if pre_process_list is None:
            pre_process_list = []
        pre_process_list = self.pre_process_list + pre_process_list
        for pp in pre_process_list:
            data, these_kwargs = pp(data, **kwargs)
            kwargs.update(these_kwargs)
            if data is None:
                return (None, kwargs)
        return (data, kwargs)

    def data_process(self, data, **kwargs):
        """Process the data.  Intended to be overridden in subclass

        Parameters
        ----------
        data : any type
            Data to be processed

        Returns
        -------
        data : any type
            Processed data
        """
        kwargs = self.kwargs_merge(**kwargs)
        # Insert call to processing code here
        return data

    def post_process(self, data,
                     post_process_list=None,
                     **kwargs):
        """Conduct post-processing tasks, including creation of metadata

        This method can be overridden to permanently insert
        post-processing tasks in the pipeline for each instantiated
        object or the post_process_list feature can be used for a more
        dynamic approach to inserting post-processing tasks at object
        instantiation and/or when the pipeline is run

        Parameters
        ----------
        data : any type
            Data to be processed by the functions in pre_process_list

        post_process_list : list
            See documentation for this parameter in Parameters section
            of :class:`BigMultiPipe`

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        (data, meta) : tuple
            Data are the post-processed data.  Meta are the combined
            meta dicts from all of the post_process_list functions.

        """
        kwargs = self.kwargs_merge(**kwargs)
        if post_process_list is None:
            post_process_list = self.post_process_list
        meta = {}
        if post_process_list is None:
            post_process_list = []
        for pp in post_process_list:
            data, this_meta = pp(data, meta, **kwargs)
            if data is None:
                return (None, {})
            meta.update(this_meta)
        return (data, meta)

    def outname_create(self, in_name, data, meta,
                       outdir=None,
                       create_outdir=None,
                       outname_append=None,
                       **kwargs):
        """Create output filename

        Parameters
        ----------
        in_name : str
            Name of input raw data file

        data : any type
            Processed data

        All other parameters : see Parameters to :class:`BigMultiPipe`

        Returns
        -------
        outname : str
            Name of output file to be written

        """
        kwargs = self.kwargs_merge(**kwargs)
        if outdir is None:
            outdir = self.outdir
        if create_outdir is None:
            create_outdir = self.create_outdir
        if outname_append is None:
            outname_append = self.outname_append
        
        if not (isinstance(in_name, str)
                and isinstance(outname_append, str)):
            raise ValueError("Not enough information provided to create output filename.  Specify outname or use an input filename and specify a string to append to that output filename to assure input is not overwritten")
        if outdir is None:
            outdir = os.getcwd()
        if create_outdir:
            os.makedirs(outdir, exist_ok=True)
        if not os.path.isdir(outdir):
            raise ValueError(f"outdir {outdir} does not exist.  Create directory or use create_outdir=True")
        bname = os.path.basename(in_name)
        prepend, ext = os.path.splitext(bname)
        outbname = prepend + outname_append + ext
        outname = os.path.join(outdir, outbname)
        return outname

def prune_pout(pout, in_names):
    """Removes entries marked for deletion in a BigMultiPipe.pipeline() output

    Parameters
    ----------
    pout : list of tuples (str or ``None``, dict)
        Output of a :meth:`BigMultiPipe.pipeline()
        <bigmultipipe.BigMultiPipe.pipeline>` run.  The `str` are
        pipeline output filenames, the `dict` is the output metadata.

    in_names : list of str
        Input file names to a :meth:`BigMultiPipe.pipeline()
        <bigmultipipe.BigMultiPipe.pipeline>` run.  There will
        be one ``pout`` for each ``in_name``

    Returns
    -------
    (pruned_pout, pruned_in_names) : list of tuples (str, dict)
        Pruned output with the ``None`` output filenames removed in both
        the ``pout`` and ``in_name`` lists.

    """
    pruned_pout = []
    pruned_in_names = []
    for i in range(len(pout)):
        if pout[i][0] is None:
            # bmp is None
            continue
        pruned_pout.append(pout[i])
        pruned_in_names.append(in_names[i])
    return (pruned_pout, pruned_in_names)


def multi_logging(level, meta, message):
    """Implements logging on a per-process basis in :class:`~bigmultipipe.BigMultiPipe` pipeline post-processing routines

    Parameters
    ----------
    level : str
        Log message level (e.g., "debug", "info", "warn, "error")

    meta : dict
        The meta channel of a :class:`~bigmultipipe.BigMultiPipe` pipeline

    message : str
        Log message

    """
    # Work directly with the meta dictionary, thus a return value
    # is not needed
    if level in meta:
        meta[level].append(message)
    else:
        meta[level] = [message]
