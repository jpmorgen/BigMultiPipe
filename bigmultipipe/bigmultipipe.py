"""Provides tools for parallel pipeline processing of large data structures"""

import os
import pickle
import multiprocessing
# For NoDaemonPool we must import this explicitly, it is not
# imported by the top-level multiprocessing module.
import multiprocessing.pool

import psutil

OUTNAME_APPEND = '_bmp'

####### NoDaemonProcess37 ######
class NoDaemonProcess37(multiprocessing.Process):
    """Used for `bigmultipipe.NoDaemonPool37`"""
    def _get_daemon(self):
        """Always returns `False`"""
        return False
    def _set_daemon(self, value):
        pass
    daemon = property(_get_daemon, _set_daemon)

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NoDaemonPool37(multiprocessing.pool.Pool):
    """For Python <=3.7,  enable child processes of
    `~multiprocessing.pool.Pool` to run their own sub-processes.  Only
    appropriate where all parents are waiting for children to finish.
    Implementation has changed in future verisons of Python 
    See discussion in
    https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic
    """
    Process = NoDaemonProcess37
####### NoDaemonProcess37 ######

####### NestablePool #########
class NoDaemonProcess(multiprocessing.Process):
    """Used for `bigmultipipe.NestablePool`"""
    @property
    def daemon(self):
        return False

    @daemon.setter
    def daemon(self, value):
        pass

class NoDaemonContext(type(multiprocessing.get_context())):
    """Used for `bigmultipipe.NestablePool`"""
    Process = NoDaemonProcess

# We sub-class multiprocessing.pool.Pool instead of multiprocessing.Pool
# because the latter is only a wrapper function, not a proper class.
class NestablePool(multiprocessing.pool.Pool):
    """For Python = 3.9(+?) enable child processes of
    `~multiprocessing.pool.Pool` to run their own sub-processes.  Only
    appropriate where all parents are waiting for children to finish.
    Implementation may change in future verison of Python
    See discussion in
    https://stackoverflow.com/questions/6974695/python-process-pool-non-daemonic

    """    
    def __init__(self, *args, **kwargs):
        kwargs['context'] = NoDaemonContext()
        super(NestablePool, self).__init__(*args, **kwargs)
####### NestablePool #########

def assure_list(x):
    """Assures x is type `list`.  ``None`` is treated as an empty list"""
    if x is None:
        x = []
    if not isinstance(x, list):
        x = [x]
    return x

def num_can_process(num_to_process=None,
                    num_processes=None,
                    mem_available=None,
                    mem_frac=0.8,
                    process_size=None,
                    error_if_zero=True):
    """Calculates maximum number of processes that can run simultaneously

    Parameters
    ----------

    num_to_process : int or ``None``, optional
        Total number of items to process.  This number is returned if
        it is less than the maximum possible simultaneous processes.
        If ``None``, not used in calculation.
        Default is ``None``

    num_processes : number or ``None``, optional
        Maximum number of parallel processes.  If ``None`` or 0, set to the
        number of physical (not logical) cores available using
        :func:`psutil.cpu_count(logical=False) <psutil.cpu_count>`.
        If less than 1, the fraction of maximum cores to use.  Default
        is ``None``

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
        not enough memory for even one process.  Set to ``False`` if
        subprocess can handle subdividing  task.
        Default is ``True``

    Returns
    -------
    num_can_process : int
        Maximum number of processes that can run simultaneously given
        input parameters


    """
    if num_processes is None or num_processes == 0:
        num_processes = psutil.cpu_count(logical=False)
    if num_processes < 0:
        raise ValueError(f'Illegal value of num_processes {num_processes}')
    if num_processes < 1:
        num_processes = max(1, round(num_processes *
                                     psutil.cpu_count(logical=False)))        
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
        raise EnvironmentError(f'Current memory {max_mem/2**20} MiB '
                               f'insufficient for process size '
                               f'{process_size/2**20} MiB.  Set '
                               'error_if_zero to False if subprocess '
                               'can handle subdividing task.')

    return min(num_to_process, num_processes, max_n)

def multi_logging(level, meta, message):
    """Implements logging on a per-process basis in
    :class:`~bigmultipipe.BigMultiPipe` pipeline post-processing routines

    Parameters
    ----------
    level : str
        Log message level (e.g., "debug", "info", "warn, "error")

    meta : dict
        The meta channel of a :class:`~bigmultipipe.BigMultiPipe` pipeline

    message : str
        Log message

    Examples
    --------
    >>> def post_process_error_example(data, bmp_meta=None, **kwargs):
    >>>     multi_logging('warning', pipe_meta, 'Example log message')


    """
    # Work directly with the meta dictionary, thus a return value
    # is not needed
    if level in meta:
        meta[level].append(message)
    else:
        meta[level] = [message]

def bmp_cleanup(data,
                bmp_meta=None,
                add=None):
    """Enables select `BigMultiPipe` metadata to be deleted after all
    `~bigmultipipe.BigMultiPipe` post-processing routines have
    completed.  

    Parameters
    ----------
    bmp_meta : dict
        `BigMultiPipe` metadata dictionary

    add : str or list of str
        `bmp_meta` keyword(s) that will be deleted

    Examples
    --------
    In a `bigmultipipe` post-processing routine add the following call
    to :func:`bmp_cleanup()` and `large_meta` will be automatically
    removed after all other post-processing routines have run.

    >>> def large_meta_producer(data, bmp_meta=None, **kwargs):
    >>>     bmp_meta['large_meta'] = 'large'
    >>>     bmp_cleanup(bmp_meta, add='large_meta')
    >>>     return data

    Notes
    -----

    As discussed in :ref:`Discussion of Design <design>`, this can be
    used to enable multiple post-processing routines to share
    information that would otherwise not be returnable on the
    `bigmultipipe` metadata stream.  One can think of this as
    implementing shared property of an object constructed on-the-fly
    by several post-processing routines.  Depending on the
    implementation, it may be more "pythonic" to create an object that
    is passed through the control stream and access that as a keyword
    in the post-processing routines.  See also
    `~bigmultipipe.BigMultiPipe.post_process_list` documentation.

    """
    cleanup_list = bmp_meta.get('bmp_cleanup_list')
    cleanup_list = assure_list(cleanup_list)
    if add is None:
        # Called from BitMultiPipe.post_process
        for c in cleanup_list:
            del bmp_meta[c]
        if len(cleanup_list) > 0:
            del bmp_meta['bmp_cleanup_list']
    else:
        add = assure_list(add)
        cleanup_list += add
        bmp_meta['bmp_cleanup_list'] = cleanup_list
    return data

def multi_proc(func, element_type=None, **kwargs):
    """Returns a function which applies func to each element in a
    (possibly nested) list.

    Parameters
    ----------
    func : function
        function to apply to items in list.  Function must have at
        least one argument (see `**kwargs`)

    element_type : type, optional
        `type` of element to which `func` will be applied.  If
        specified, allows nested lists of files to be processed        

    **kwargs : passed to func
        
    Returns
    -------
    function

    Examples
    --------
    >>> def plus1(data, **kwargs):
    >>>     return data + 1
    >>>
    >>> def multi_plus1(data, **kwargs):
    >>>     return multi_proc(plus1)(data)

    Notes
    -----
    This function is useful when the list of `bigmultipipe` `in_names`
    is not just a list of single files, but a list of possibly nested
    lists and certain pre- and post-processing routines are best
    applied to the individual elements of those lists (e.g. individual
    files)

    It is syntactically correct to use multi_proc to define a function
    on-the-fly, e.g.:

    >>> newfunc = multi_proc(plus1)

    however that function becomes a member of `locals` and cannot be
    pickled for passing in a multiprocessing environment.  The form in
    `Examples` avoids the pickling error.  See 
    https://stackoverflow.com/questions/52265120/python-multiprocessing-pool-attributeerror

    """
    if element_type is None:
        # Nominal case, just a straight list of data items in data_list 
        def ret_func(data_list, **kwargs):
            return [func(data, **kwargs) for data in data_list]
        return ret_func
    # If we know element_type, we can get fancy with nested lists
    def ret_func(data_list, **kwargs):
        ret_list = []
        for data in data_list:
            if isinstance(data, element_type):
                ret_list.append(func(data, **kwargs))
            else:
                ret_list.append(ret_func(data, **kwargs))
        return ret_list
    return ret_func

def no_outfile(data, **kwargs):
    """`bigmultipipe` post-processing routine that stops pipeline processing and returns accumulated metadata without writing any output files.  Put last in `BigMultiPipe.post_process_list`
    """
    return None

def cached_pout(pipe_code,
                poutname=None,
                read_pout=False,
                write_pout=False,
                create_outdir=False,
                **kwargs):
    """Write/read :meth:`BigMultiPipe.pipeline()` metadata output
    ("pout") to/from a file using `pickle`

    Parameters
    ----------
    pipe_code : function
        Function that executes `bigmultipipe` pipeline if `read_pout`
        is ``False`` or `poutname` cannot be read.  Must return
        pipeline metadata output ("pout")

    poutname : str
        Filename to be read/written

    read_pout : bool
        If `True` read pipeline output from `poutname`
        Default is `False`

    write_pout : bool
        If `True` write pipeline output to `poutname`
        Default is `False`

    create_outdir : bool, optional
        If ``True``, create any needed parent directories into which
        poutname is to be saved.  This parameter is passed along to
        pipe_code because it need not write the pipeline output files
        to the same directory as poutname
        Default is ``False``

    **kwargs : keyword arguments to pass to `pipe_code`

    Returns
    -------
    pout : dict
        Pipeline metadata output

    """
    if read_pout:
        try:
            pout = pickle.load(open(poutname, "rb"))
            return pout
        except:
            #log.debug(f'running code because file not found: {read_pout}')
            pass
    # Allow for pout to be written to a different place than pipeline's outdir
    pout = pipe_code(create_outdir=create_outdir, **kwargs)
    if write_pout:
        if create_outdir:
            os.makedirs(os.path.dirname(poutname), exist_ok=True)
        pickle.dump(pout, open(poutname, "wb"))
    return pout
    
def prune_pout(pout, in_names):
    """Removes entries marked for deletion in a
    :meth:`BigMultiPipe.pipeline()` output

    To mark an entry for deletion, ``outfname`` must be `None` *and*
    ``meta`` must be `{}`

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
        if pout[i][0] is None and pout[i][1] == {}:
            # outfname AND meta are empty
            continue
        pruned_pout.append(pout[i])
        pruned_in_names.append(in_names[i])
    return (pruned_pout, pruned_in_names)

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

class BigMultiPipe():
    """Base class for memory- and processing power-optimized pipelines

    Parameters
    ----------
    outdir, create_outdir, outname_append, outname: see
        :meth:`~BigMultiPipe.outname_create`

    num_processes, mem_available, mem_frac, process_size : optional
        These parameters tune computer processing and memory resources
        and are used when the :meth:`pipeline` method is executed.
        See documentation for :func:`num_can_process` for use, noting
        that the ``num_to_process`` argument of that function is
        set to the number of input filenames in :meth:`pipeline`

    pre_process_list : list
        See `~BigMultiPipe.pre_process_list` attribute

    post_process_list : list
        See `~BigMultiPipe.post_process_list` attribute

    PoolClass : class name or None, optional

        Typcally a subclass of :class:`multiprocessing.pool.Pool`. The
        :meth:`~multiprocessing.pool.Pool.map()` method of this class
        implements the multiprocessing feature of this module.  If
        ``None``, :class:`multiprocessing.pool.Pool` is used.  Default is
        ``None.``

    \*\*kwargs : optional

        Python's ``**kwargs`` construct stores additional keyword
        arguments as a `dict` accessed in the function as ``kwargs``.
        In order to implement the control stream discussed in the
        introduction to this module, this `dict` is captured as
        property on instantiation.  When any methods are run, the
        ``kwargs`` passed to that method are merged with the property
        ``kwargs`` using :meth:`~BigMultiPipe.kwargs_merge()`.  This
        allows the parameters passed to the methods at runtime to
        override the parameters passed to the object at instantiation
        time.

    Notes
    -----

    Just like ``**kwargs``, all named parameters passed at object
    instantiation are stored as property and used to initialize the
    identical list of parameters to the :func:`BigMultiPipe.pipeline`
    method.  Any of these parameters *except* ``pre_process_list`` and
    ``post_process_list`` can be overridden when
    :func:`~BigMultiPipe.pipeline` is called by using the
    corresponding keyword.  This enables definition of a default
    pipeline configuration when the object is instantiated that can be
    modified at run-time.  The exception to this are
    ``pre_process_list`` and ``post_process_list``.  When these are
    provided to :func:`~BigMultiPipe.pipeline`, they are added to
    corresponding lists provided at instantiation time.  To erase
    these lists in the object simply set their property to None:
    e.g. `BigMultipipe.pre_process_list` = None

    """
    def __init__(self,
                 num_processes=None,
                 mem_available=None,
                 mem_frac=0.8,
                 process_size=None,
                 outdir=None,
                 create_outdir=False,
                 outname_append=OUTNAME_APPEND,
                 pre_process_list=None,
                 post_process_list=None,
                 PoolClass=None,
                 **kwargs):
        self.num_processes = num_processes
        self.mem_available = mem_available
        self.mem_frac = mem_frac
        self.process_size = process_size
        self.pre_process_list = pre_process_list
        self.post_process_list = post_process_list
        if PoolClass is None:
            PoolClass = multiprocessing.Pool
        self.PoolClass = PoolClass
        self.outdir = outdir
        self.create_outdir = create_outdir
        self.outname_append = outname_append
        self.kwargs = kwargs

    @property
    def pre_process_list(self):
        """ list or None : List of pre-processing routines

        List of functions called by :func:`pre_process` before primary
        processing step.  Intended to implement filtering and control
        features as described in :ref:`Discussion of Design <design>`.
        Each function must accept one positional parameter, ``data``,
        keyword arguments necessary for its internal functioning, and
        ``**kwargs`` to ignore keyword parameters not processed by the
        function.  If the return value of the function is ``None``,
        processing of that file stops, no output file is written, and
        ``None`` is returned instead of an output filename.  This is
        how filtering is implemented.  Otherwise, the return value is
        either ``data`` or a `dict` with two keys: ``bmp_data`` and
        ``bmp_kwargs``.  In the later case, ``bmp_kwargs`` will be
        merged into ``**kwargs``.  This is how the control channel is
        implemented.  Below are examples.  See :ref:`Example` to see
        this code in use in a functioning pipeline.

	>>> def reject(data, reject_value=None, **kwargs):
	>>>     if reject_value is None:
	>>>         return data
	>>>     if data[0,0] == reject_value:
	>>>         # --> Return data=None to reject data
	>>>         return None
	>>>     return data
	>>> 
	>>> def boost_later(data, boost_target=None, boost_amount=None, **kwargs):
	>>>     if boost_target is None or boost_amount is None:
	>>>         return data
	>>>     if data[0,0] == boost_target:
	>>>         add_kwargs = {'need_to_boost_by': boost_amount}
	>>>         retval = {'bmp_data': data,
	>>>                   'bmp_kwargs': add_kwargs}
	>>>         return retval
	>>>     return data

        """
        return self._pre_process_list

    @pre_process_list.setter
    def pre_process_list(self, value):
        self._pre_process_list = assure_list(value)

    @property
    def post_process_list(self):
        """
        list or None : List of post-processing routines

        List of functions called by :func:`post_process` after primary
        processing step.  Indended to enable additional processing
        steps and produce metadata as discussed in :ref:`Discussion of
        Design <design>`.  Each function must accept one positional
        parameter, ``data``, one optional keyword parameter,
        ``bmp_meta``, any keywords needed by the function, and an
        arbitrary list of keywords handled by the ``**kwargs``
        feature.  ``bmp_meta`` is of type `dict`.  The return value of
        each function is intended to be the data but it not restricted
        in any way.  If ``None`` is return, processing stops for that
        file, ``None`` is returned for that file's data and the
        metadata accumulated to that point is returned as that file's
        metadata.  :meth:`bmp_meta.clear() <dict.clear()>` can be used
        in the terminating ``post_process_list`` routine if it is
        desirable to erase the metadata.  See :ref:`Example` for
        examples of a simple functioning pipeline.

	>>> def later_booster(data, need_to_boost_by=None, **kwargs):
	>>>     if need_to_boost_by is not None:
	>>>         data = data + need_to_boost_by
	>>>     return data
	>>> 
	>>> def median(data, bmp_meta=None, **kwargs):
	>>>     m = np.median(data)
	>>>     if bmp_meta is not None:
	>>>         bmp_meta['median'] = m
	>>>     return data
	>>> 

        """
        return self._post_process_list

    @post_process_list.setter
    def post_process_list(self, value):
        self._post_process_list = assure_list(value)

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
                 outdir=None,
                 create_outdir=None,
                 outname_append=None,
                 outname=None,
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

        pout : `list` of tuples ``(outname, meta)``, one `tuple` for
            each ``in_name``.  ``Outname`` is `str` or ``None``,
            ``meta`` is a `dict` containing metadata output.  If
            ``outname`` is `str`, it is the name of the file to which
            the processed data were written.  If ``None`` *and* meta =
            {}, the convenience function :func:`prune_pout` can be
            used to remove this tuple from ``pout`` and the
            corresponding in_name from the in_names list.

        """
        num_processes = num_processes or self.num_processes
        mem_available = mem_available or self.mem_available
        mem_frac = mem_frac or self.mem_frac
        process_size = process_size or self.process_size
        PoolClass = PoolClass or self.PoolClass
        outdir = outdir or self.outdir
        create_outdir = create_outdir or self.create_outdir
        outname_append = outname_append or self.outname_append
        kwargs = self.kwargs_merge(**kwargs)
        ncp = num_can_process(len(in_names),
                              num_processes=num_processes,
                              mem_available=mem_available,
                              mem_frac=mem_frac,
                              process_size=process_size)
        wwk = WorkerWithKwargs(self.file_process, outdir=outdir,
                               create_outdir=create_outdir,
                               outname_append=outname_append,         
                               **kwargs)
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
        (data, add_kwargs) = self.pre_process(data, **kwargs)
        if data is None:
            return (None, {})
        kwargs.update(add_kwargs)
        data, meta = \
            self.data_process_meta_create(data, in_name=in_name, **kwargs)
        if data is None:
            return (None, meta)
        # Make data and meta available for convenience for subclasses.
        outname = self.outname_create(in_name, data=data, meta=meta, **kwargs)
        outname = self.file_write(data, outname, meta=meta,
                                  in_name=in_name, **kwargs)
        return (outname, meta)

    def file_read(self, in_name, **kwargs):
        """Reads data file(s) from disk.  Intended to be overridden by subclass

        Parameters
        ----------
        in_name : str or list
            If `str`, name of file to read.  If `list`, each element
            in list is processed recursively so that multiple files
            can be considered a single "data" in `bigmultipipe`
            nomenclature

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        data : any type
            Data to be processed

        """
        kwargs = self.kwargs_merge(**kwargs)
        if isinstance(in_name, str):
            with open(in_name, 'rb') as f:
                data = f.read()
            return data
        # Allow list (of lists...) to be read into a "data"
        return [self.file_read(name, **kwargs)
                for name in in_name]

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
        data = self.data_process(data, **kwargs)
        if data is None:
            return(None, {})
        data, meta = self.post_process(data, **kwargs)
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
        pre_process_list = assure_list(pre_process_list)
        pre_process_list = self.pre_process_list + pre_process_list
        for pp in pre_process_list:
            retval = pp(data, **kwargs)
            if retval is None:
                return (None, {})
            if isinstance(retval, dict) and 'bmp_data' in retval:
                data = retval['bmp_data']
                these_kwargs = retval.get('bmp_kwargs')
                if these_kwargs is None:
                    these_kwargs = {}
                kwargs.update(these_kwargs)
            else:
                # Data might be a dict
                data = retval
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
        # --> Insert call to processing code here
        return data

    def post_process(self, data,
                     post_process_list=None,
                     no_bmp_cleanup=False,
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

        no_bmp_cleanup : bool
            Do not run `bmp_cleanup` post-processing task even if
            keywords have been added to the bmp_cleanup_list (provided
            for debugging purposes).
            Default is `False`

        kwargs : see Notes in :class:`BigMultiPipe` Parameter section

        Returns
        -------
        (data, meta) : tuple
            Data are the post-processed data.  Meta are the combined
            meta dicts from all of the post_process_list functions.

        """
        kwargs = self.kwargs_merge(**kwargs)
        post_process_list = assure_list(post_process_list)
        post_process_list = self.post_process_list + post_process_list
        meta = {}
        for pp in post_process_list:
            data = pp(data, bmp_meta=meta, **kwargs)
            if data is None:
                # Stop our pipeline, but remember to clean up!
                break
        if not no_bmp_cleanup:
            data = bmp_cleanup(data, bmp_meta=meta)
        return (data, meta)

    def outname_create(self, in_name,
                       outdir=None,
                       create_outdir=None,
                       outname_append=None,
                       outname=None,
                       meta=None,
                       **kwargs):
        """Create output filename (including path)

        Parameters
        ----------
        in_name : str
            Name of input raw data file.  The basename of this file is
            used together with contents of other parameters to
            construct the output filename.  Overwritten by `outname.` 

        outdir : str, None, optional
            Name of directory into which output files will be written.  If
            `None`, current directory in which the Python process is
            running will be used.  Overwritten by ``outdir`` key in
            `meta`, ignored if `outname` is specified and contains a
            full path.
            Default is ``None``

        create_outdir : bool, optional
            If ``True``, create outdir and any needed parent directories.
            Does not raise an error if outdir already exists.
            Overwritten by ``create_outdir`` key in `meta`. 
            Default is ``False``

        outname_append : str, optional
            String to append to outname to avoid risk of input file
            overwrite.  Example input file ``test.dat`` would become
            output file ``test_bmp.dat``.  Overwritten by
            ``outname_append key`` in `meta`.  Ignored if `outname` is
            specified.
            Default is ``_bmp``

        outname : str
            Output filename.  It would be unusual to specify this at
            instantiation of a :class:`BigMultiPipe` object, since all
            files would be written to only this one filename.  Rather,
            this is intended to be generated by a pre-processing step
            or overwritten by the ``outname`` key in `meta`.
            Default is ``None``

        meta : dict
            Metadata generated by `bigmultipipe` pipeline.  Keys from
            `meta` are used to overwrite the keywords of this method,
            as noted above.
            Default is ``None``

        Returns
        -------
        outname : str
            output filename to be written, including path

        Raises
        ------
        ValueError if not enough information is specified to construct
        outname or the directory into which the file is to be written does
        not exist (see `create_outdir` to prevent the later error)

        Notes
        -----
        meta['outname'] is how outnames need to be specified when
        `in_name` contains multiple files

        """
        kwargs = self.kwargs_merge(**kwargs)
        if meta is not None:
            outdir = meta.get('outdir') or outdir 
            create_outdir = meta.get('create_outdir') or create_outdir 
            outname_append = meta.get('outname_append') or outname_append 
            outname = meta.get('outname') or outname

        return outname or outname_creator(in_name,
                                          outdir=outdir,
                                          create_outdir=create_outdir,
                                          outname_append=outname_append)

        if outname is not None:
            outdir = os.path.dirname(outname) or outdir
        outdir = outdir or os.getcwd()
        if create_outdir:
            os.makedirs(outdir, exist_ok=True)
        # I think it is more pythonic to just let this fail on write,
        # since the user may not care if the directory is written
        #if not os.path.isdir(outdir):
        #    raise ValueError(f"outdir {outdir} does not exist.  Create directory or use create_outdir=True")

        if outname is None:
            bname = os.path.basename(in_name)
            prepend, ext = os.path.splitext(bname)
            outbname = prepend + outname_append + ext
        else:
            outbname = os.path.basename(outname)
        outname = os.path.join(outdir, outbname)
        return outname

def outname_creator(in_name,
                    outdir=None,
                    create_outdir=False,
                    outname_append=''):
    """Create output filename (including path) from in_name"""
    
    outdir = outdir or os.getcwd()
    if create_outdir:
        os.makedirs(outdir, exist_ok=True)
    bname = os.path.basename(in_name)
    prepend, ext = os.path.splitext(bname)
    outbname = prepend + outname_append + ext
    outname = os.path.join(outdir, outbname)
    return outname

