.. _use:

Discussion of use
-----------------

The `bigmultipipe` module provides tools that enable a flexible,
modular approach to constructing data processing pipelines that
optimize computer processing, memory, and disk I/O resources.  The
:class:`~bigmultipipe.BigMultiPipe` base class is subclassed by the
user to connect the file reading, file writing, and data processing
methods to the user's existing processing code.  The
:meth:`BigMultiPipe.pipeline() <bigmultipipe.BigMultiPipe.pipeline>`
method runs the pipeline, maximizing the host computer's processing
resources.  Keywords are available to tailor memory and processor use,
the most important of which being ``process_size``, the maximum size
in bytes of an individual process.  Two optional keywords,
``pre_process_list`` and ``post_process_list`` can contain lists of
functions to be run on the data before and after the primary
processing step.  These keywords enable additional flexibility in the
creation and modification of the pipeline at object instantiation
and/or pipeline runtime.

.. _design:

Discussion of Design
--------------------

The `bigmultipipe` module uses a three-stream approach to address the
problem of parallel processing large data structures.  Stream (1) is
the data, which begins and ends on disk, thus side-stepping the issues
of inter-process communication discussed in the `Background`_ section.
Stream (2) is control.  This stream is intended to control the primary
processing step, but can also control pre-processing, post processing,
file name creation and file writing.  The control stream starts as the
keywords that are provided to a :class:`~bigmultipipe.BigMultiPipe`
object on instantiation.  Using Python's flexible ``**kwarg`` feature,
these keywords can be supplemented or overridden when the
:meth:`BigMultiPipe.pipeline() <bigmultipipe.BigMultiPipe.pipeline>`
method is called.  The functions in ``pre_process_list`` can similarly
supplement or override these keywords.  Finally, there is stream (3),
the output metadata.  Stream (3) is returned to the caller along with
the output filename of each processed file for use in subsequent
processing steps.  Stream (3) can be used to minimize the number of
times the large output data files are re-read during subsequent
processing.  That said, as discussed in the `Background`_ section, the
amount of information returned as metadata should be modest in size.

.. _background:

Background
----------

The parallel pipeline processing of large data structures is best done
in a multithreaded environment, which enables the data to be easily
shared between threads executing in the same process.  Unfortunately,
Python's `Global Interpreter Lock (GIL)`_ prevents multiple threads
from running at the same time, except in certain cases, such as I/O
wait and some `numpy` array operations.  Python's `multiprocessing`
module provides a partial solution to the GIL dilemma.  The
`multiprocessing` module launches multiple independent Python
processes, thus providing true concurrent parallel processing in a way
that does not depend on the underlying code being executed.  The
multiprocessing module also provides tools such as
:func:`multiprocessing.Pipe` and :class:`multiprocessing.Queue` that
enable communication between these processes.  Unfortunately, these
inter-process communication solutions are not quite as flexible as
shared memory between threads in one process because data must be
transferred.  The transfer is done using `pickle`: data are pickled on
one end of the pipe and unpickled on the other.  Depending on the
complexity and size of the object, the pickle/unpickle process can be
very inefficient.  The `bigmultipipe` module provides a basic
framework for avoiding all of these problems by implementing the
three-stream approach described in the `Discussion of Design`_
section.  Interprocess communication requiring `pickle` still occurs,
however, only filenames and (hopefully) modest-sized metadata is
exchanged in this way.


.. _Global Interpreter Lock (GIL): https://wiki.python.org/moin/GlobalInterpreterLock


Statement of scope
------------------

This module is best suited for the simple case of a "straight through"
pipeline: one input file to one output file.  For more complicated
pipeline topologies, the `MPipe`_ module may be useful.  For parallel
processing of loops that include certain `numpy` operations and other
optimization tools, `numba`_ may be useful.  Although it has yet to be
tested, `bigmultipipe` should be mutually compatible with either or
both of these other packages, although the
:class:`bigmultipipe.NoDaemonPool` version of
:class:`multiprocessing.pool.Pool` may need to be used if multiple
levels of multiprocessing are being conducted.

.. _MPipe: https://vmlaker.github.io/mpipe/
.. _numba: https://numba.pydata.org/ 

.. _example:

Example
-------

The following code shows how to develop a `bigmultipipe` pipeline
starting from code that processes large files one at a time in a
simple for loop.

First the `for` loop case:

>>> import os
>>> from tempfile import TemporaryDirectory, TemporaryFile
>>> import numpy as np
>>> 
>>> from bigmultipipe import BigMultiPipe, prune_pout
>>> 
>>> # Write some large files
>>> with TemporaryDirectory() as tmpdirname:
>>>     in_names = []
>>>     for i in range(10):
>>>         outname = f'big_array_{i}.npy'
>>>         outname = os.path.join(tmpdirname, outname)
>>>         a = i + np.zeros((1000,2000))
>>>         np.save(outname, a)
>>>         in_names.append(outname)
>>> 
>>>     # Process with traditional for loop
>>>     reject_value = 2
>>>     boost_target=3
>>>     boost_amount=5
>>>     outnames = []
>>>     meta = []
>>>     for f in in_names:
>>>         # File read step
>>>         data = np.load(f)
>>>         # Pre-processing steps
>>>         if data[0,0] == reject_value: 
>>>             continue
>>>         if data[0,0] == boost_target:
>>>             flag_to_boost_later = True
>>>         else:
>>>             flag_to_boost_later = False
>>>         # Processing step
>>>         data = data * 10
>>>         # Post-processing steps
>>>         if flag_to_boost_later:
>>>             data = data + boost_amount
>>>         meta.append({'average': np.average(data)})
>>>         outname = f + '_bmp'
>>>         np.save(outname, data)
>>>         outnames.append(outname)
>>>     cleaned_outnames = [os.path.basename(f) for f in outnames]
>>>     cleaned_pout = zip(cleaned_outnames, meta)
>>>     print(list(cleaned_pout))
[('big_array_0.npy_bmp', {'average': 0.0}), ('big_array_1.npy_bmp', {'average': 10.0}), ('big_array_3.npy_bmp', {'average': 35.0}), ('big_array_4.npy_bmp', {'average': 40.0}), ('big_array_5.npy_bmp', {'average': 50.0}), ('big_array_6.npy_bmp', {'average': 60.0}), ('big_array_7.npy_bmp', {'average': 70.0}), ('big_array_8.npy_bmp', {'average': 80.0}), ('big_array_9.npy_bmp', {'average': 90.0})] # doctest: +STR_CMP

Now lets parallelize with `bigmultipipe` a few different ways:

(1) Put all code into methods in a subclass of :class:`~bigmultipipe.BigMultiPipe`

>>> class DemoMultiPipe1(BigMultiPipe):
>>> 
>>>     def file_read(self, in_name, **kwargs):
>>>         data = np.load(in_name)
>>>         return data
>>> 
>>>     def file_write(self, data, outname, **kwargs):
>>>         np.save(outname, data)
>>>         return outname
>>> 
>>>     def data_process_meta_create(self, data,
>>>                                  reject_value=None,
>>>                                  boost_target=None,
>>>                                  boost_amount=0,
>>>                                  **kwargs):
>>>         # Pre-processing steps
>>>         if reject_value is not None:
>>>             if data[0,0] == reject_value: 
>>>                 return (None, {})
>>>         if (boost_target is not None
>>>             and data[0,0] == boost_target):
>>>                 flag_to_boost_later = True
>>>         else:
>>>             flag_to_boost_later = False
>>>         # Processing step
>>>         data = data * 10
>>>         # Post-processing steps
>>>         if flag_to_boost_later:
>>>             data = data + boost_amount
>>>         meta = {'average': np.average(data)}
>>>         return (data, meta)
>>> 
>>> # Write large files and process with DemoMultiPipe1
>>> with TemporaryDirectory() as tmpdirname:
>>>     in_names = []
>>>     for i in range(10):
>>>         outname = f'big_array_{i}.npy'
>>>         outname = os.path.join(tmpdirname, outname)
>>>         a = i + np.zeros((1000,2000))
>>>         np.save(outname, a)
>>>         in_names.append(outname)
>>> 
>>>     dmp = DemoMultiPipe1(boost_target=3, outdir=tmpdirname)
>>>     pout = dmp.pipeline(in_names, reject_value=2,
>>>                         boost_amount=5)
>>> 
>>> # Prune outname ``None`` and remove directory
>>> pruned_pout, pruned_in_names = prune_pout(pout, in_names)
>>> pruned_outnames, pruned_meta = zip(*pruned_pout)
>>> pruned_outnames = [os.path.basename(f) for f in pruned_outnames]
>>> pruned_in_names = [os.path.basename(f) for f in pruned_in_names]
>>> pretty_print = zip(pruned_in_names, pruned_outnames, meta)
>>> print(list(pretty_print))
[('big_array_0.npy', 'big_array_0_bmp.npy', {'average': 0.0}), ('big_array_1.npy', 'big_array_1_bmp.npy', {'average': 10.0}), ('big_array_3.npy', 'big_array_3_bmp.npy', {'average': 35.0}), ('big_array_4.npy', 'big_array_4_bmp.npy', {'average': 40.0}), ('big_array_5.npy', 'big_array_5_bmp.npy', {'average': 50.0}), ('big_array_6.npy', 'big_array_6_bmp.npy', {'average': 60.0}), ('big_array_7.npy', 'big_array_7_bmp.npy', {'average': 70.0}), ('big_array_8.npy', 'big_array_8_bmp.npy', {'average': 80.0}), ('big_array_9.npy', 'big_array_9_bmp.npy', {'average': 90.0})] # doctest: +STR_CMP

.. note::
   We override
   :meth:`~bigmultipipe.BigMultiPipe.data_process_meta_create`
   because we are both processing data *and* creating metadata

.. note::

   The ``outname_append`` parameter and
   :meth:`~bigmultipipe.BigMultiPipe.outname_create` method of
   :class:`~bigmultipipe.BigMultiPipe` make it easy to tailor the look
   of the output filenames.  The convenience function
   :func:`~bigmultipipe.prune_pout` makes it easy to keep the input
   and output filename lists syncronized when files are rejected

(2) Let's use the ``pre_process_list`` and ``post_process_list``
    parameters.  This allows us to assemble a pipeline at object
    instantiation time or pipeline run time:x


>>> def reject(data, reject_value=None, **kwargs):
>>>     """Example pre-processing function to reject data"""
>>>     if reject_value is None:
>>>         return (data, {})
>>>     if data[0,0] == reject_value:
>>>         # --> Return data=None to reject data
>>>         return (None, {})
>>>     return (data, {})
>>> 
>>> def boost_later(data, boost_target=None, boost_amount=None, **kwargs):
>>>     """Example pre-processing function that shows how to alter kwargs"""
>>>     if boost_target is None or boost_amount is None:
>>>         return (data, {})
>>>     if data[0,0] == boost_target:
>>>         # --> This is equivalent to setting a keyword parameter
>>>         # need_to_boost_by=boost_amount
>>>         return (data, {'need_to_boost_by': boost_amount})
>>>     return (data, {})
>>> 
>>> def later_booster(data, meta, need_to_boost_by=None, **kwargs):
>>>     """Example post-processing function.  Interprets keyword set by boost_later"""
>>>     if need_to_boost_by is None:
>>>         return (data, {})
>>>     data = data + need_to_boost_by
>>>     return (data, {})
>>> 
>>> def average(data, meta, **kwargs):
>>>     """Example metadata generator"""
>>>     av = np.average(data)
>>>     return (data, {'average': av})
>>> 
>>> class DemoMultiPipe2(BigMultiPipe):
>>> 
>>>     def file_read(self, in_name, **kwargs):
>>>         data = np.load(in_name)
>>>         return data
>>> 
>>>     def file_write(self, data, outname, **kwargs):
>>>         np.save(outname, data)
>>>         return outname
>>> 
>>>     def data_process(self, data, **kwargs):
>>>         return data * 10
>>>     
>>> # Write large files and process with DemoMultiPipe2
>>> with TemporaryDirectory() as tmpdirname:
>>>     in_names = []
>>>     for i in range(10):
>>>         outname = f'big_array_{i}.npy'
>>>         outname = os.path.join(tmpdirname, outname)
>>>         a = i + np.zeros((1000,2000))
>>>         np.save(outname, a)
>>>         in_names.append(outname)
>>> 
>>>     # Create a pipeline using the pre- and post-processing
>>>     # components defined above.  This enables pipeline is to be
>>>     # assembled at instantiation and controlled at either
>>>     # instantiation or runtime 
>>>     dmp = DemoMultiPipe2(pre_process_list=[reject, boost_later],
>>>                          post_process_list=[later_booster, average],
>>>                          boost_target=3, outdir=tmpdirname)
>>>     pout = dmp.pipeline(in_names, reject_value=2,
>>>                         boost_amount=5)
>>> 
>>> # Prune outname ``None`` and remove directory
>>> pruned_pout, pruned_in_names = prune_pout(pout, in_names)
>>> pruned_outnames, pruned_meta = zip(*pruned_pout)
>>> pruned_outnames = [os.path.basename(f) for f in pruned_outnames]
>>> pruned_in_names = [os.path.basename(f) for f in pruned_in_names]
>>> pretty_print = zip(pruned_in_names, pruned_outnames, meta)
>>> print(list(pretty_print))
[('big_array_0.npy_bmp', {'average': 0.0}), ('big_array_1.npy_bmp', {'average': 10.0}), ('big_array_3.npy_bmp', {'average': 35.0}), ('big_array_4.npy_bmp', {'average': 40.0}), ('big_array_5.npy_bmp', {'average': 50.0}), ('big_array_6.npy_bmp', {'average': 60.0}), ('big_array_7.npy_bmp', {'average': 70.0}), ('big_array_8.npy_bmp', {'average': 80.0}), ('big_array_9.npy_bmp', {'average': 90.0})] # doctest: +STR_CMP

.. note::
   In case (2), we just need to override the
   :meth:`~bigmultipipe.BigMultiPipe.data_process` method, since the
   ``pre_process_list`` and ``post_process_list`` routines handle all
   the rest.

.. note::
   
   When working with the ``post_process_list`` routines, or ``meta`` in
   general, the ``meta`` `dict` itself can be modified rather than just
   creating a small dictionary for merging.  Here is `average`
   written two different ways, both of which are equivalent because of
   the way :meth:`~bigmultipipe.BigMultiPipe.data_post_process` merges
   the ``meta`` return value using :meth:`dict.update`:

   >>> def average(data, meta, **kwargs):
   >>>     av = np.average(data)
   >>>     meta['average'] = av
   >>>     return (data, {})

   >>> def average(data, meta, **kwargs):
   >>>     av = np.average(data)
   >>>     meta['average'] = av
   >>>     return (data, meta)

.. note::
   
   The trick for modifying the ``meta`` `dict` on-the-fly in the
   previous note does not work for ``**kwargs``.  Because of the magic
   of how Python implements ``**kwargs``, ``kwargs`` in the called
   routine effectively becomes a `dict` of keywords that is passed by
   value.  Nevertheless, it is possible to querey and extract existing
   keywords from ``kwargs`` and return them to
   :meth:`~bigmultipipe.BigMultiPipe.pre_process` for merging into the
   ``kwargs`` that are passed to subsequent routines.  This provides
   one mechanism for implementing the "control" channel of
   `bigmultipipe`, as discussed in `Discussion of Design`_.  Another
   method is to define property in the subclassed
   :class:`~bigmultipipe.BigMultiPipe`.  The advantage of using the
   ``**kwargs``-based control channel is that the components that
   control it can be assembled via the ``pre_preocess_list`` mechanism
   at runtime, thus providing a mechanism for algorithmic control of
   the pipeline construction process.
