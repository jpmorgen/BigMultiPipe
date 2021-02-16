"""bigmultipipe example code showing evolution from traditional for loop

"""

import os
from tempfile import TemporaryDirectory, TemporaryFile
import numpy as np

from bigmultipipe import BigMultiPipe, prune_pout

# Write some large files
with TemporaryDirectory() as tmpdirname:
    in_names = []
    for i in range(10):
        outname = f'big_array_{i}.npy'
        outname = os.path.join(tmpdirname, outname)
        a = i + np.zeros((1000,2000))
        np.save(outname, a)
        in_names.append(outname)

    # Process with traditional for loop
    reject_value = 2
    boost_target=3
    boost_amount=5
    outnames = []
    meta = []
    for f in in_names:
        # File read step
        data = np.load(f)
        # Pre-processing steps
        if data[0,0] == reject_value: 
            continue
        if data[0,0] == boost_target:
            flag_to_boost_later = True
        else:
            flag_to_boost_later = False
        # Processing step
        data = data * 10
        # Post-processing steps
        if flag_to_boost_later:
            data = data + boost_amount
        meta.append({'median': np.median(data),
                     'average': np.average(data)})
        outname = f + '_bmp'
        np.save(outname, data)
        outnames.append(outname)
    cleaned_innames = [os.path.basename(f) for f in in_names]
    cleaned_outnames = [os.path.basename(f) for f in outnames]
    cleaned_pout = zip(cleaned_innames, cleaned_outnames, meta)
    print(list(cleaned_pout))

# BigMultiPipe object for parallel processing above code, case (1)
class DemoMultiPipe1(BigMultiPipe):

    def file_read(self, in_name, **kwargs):
        data = np.load(in_name)
        return data

    def file_write(self, data, outname, **kwargs):
        np.save(outname, data)
        return outname

    def data_process_meta_create(self, data,
                                 reject_value=None,
                                 boost_target=None,
                                 boost_amount=0,
                                 **kwargs):
        # Pre-processing steps
        if reject_value is not None:
            if data[0,0] == reject_value: 
                return (None, {})
        if (boost_target is not None
            and data[0,0] == boost_target):
                flag_to_boost_later = True
        else:
            flag_to_boost_later = False
        # Processing step
        data = data * 10
        # Post-processing steps
        if flag_to_boost_later:
            data = data + boost_amount
        meta = {'median': np.median(data),
                'average': np.average(data)}
        return (data, meta)

# Write large files and process with DemoMultiPipe1
with TemporaryDirectory() as tmpdirname:
    in_names = []
    for i in range(10):
        outname = f'big_array_{i}.npy'
        outname = os.path.join(tmpdirname, outname)
        a = i + np.zeros((1000,2000))
        np.save(outname, a)
        in_names.append(outname)

    dmp = DemoMultiPipe1(boost_target=3, outdir=tmpdirname)
    pout = dmp.pipeline(in_names, reject_value=2,
                        boost_amount=5)

# Prune outname ``None`` and remove directory
pruned_pout, pruned_in_names = prune_pout(pout, in_names)
pruned_outnames, pruned_meta = zip(*pruned_pout)
pruned_outnames = [os.path.basename(f) for f in pruned_outnames]
pruned_in_names = [os.path.basename(f) for f in pruned_in_names]
pretty_print = zip(pruned_in_names, pruned_outnames, meta)
print(list(pretty_print))
    
# BigMultiPipe object for parallel processing above code, case (2)
def reject(data, reject_value=None, **kwargs):
    """Example pre-processing function to reject data"""
    if reject_value is None:
        return data
    if data[0,0] == reject_value:
        # --> Return data=None to reject data
        return None
    return data

def boost_later(data, boost_target=None, boost_amount=None, **kwargs):
    """Example pre-processing function that shows how to alter kwargs"""
    if boost_target is None or boost_amount is None:
        return data
    if data[0,0] == boost_target:
        add_kwargs = {'need_to_boost_by': boost_amount}
        retval = {'bmp_data': data,
                  'bmp_kwargs': add_kwargs}
        return retval
    return data

def later_booster(data, need_to_boost_by=None, **kwargs):
    """Example post-processing function.  Interprets keyword set by boost_later"""
    if need_to_boost_by is not None:
        data = data + need_to_boost_by
    return data

def median(data, bmp_meta=None, **kwargs):
    """Example metadata generator"""
    median = np.median(data)
    if bmp_meta is not None:
        bmp_meta['median'] = median
    return data

def average(data, bmp_meta=None, **kwargs):
    """Example metadata generator"""
    av = np.average(data)
    local_meta = {'average': av}
    if bmp_meta is not None:
        bmp_meta.update(local_meta)
    return data

class DemoMultiPipe2(BigMultiPipe):

    def file_read(self, in_name, **kwargs):
        data = np.load(in_name)
        return data

    def file_write(self, data, outname, **kwargs):
        np.save(outname, data)
        return outname

    def data_process(self, data, **kwargs):
        return data * 10
    
# Write large files and process with DemoMultiPipe2
with TemporaryDirectory() as tmpdirname:
    in_names = []
    for i in range(10):
        outname = f'big_array_{i}.npy'
        outname = os.path.join(tmpdirname, outname)
        a = i + np.zeros((1000,2000))
        np.save(outname, a)
        in_names.append(outname)

    # Create a pipeline using the pre- and post-processing
    # components defined above.  This enables pipeline is to be
    # assembled at instantiation and controlled at either
    # instantiation or runtime 
    dmp = DemoMultiPipe2(pre_process_list=[reject, boost_later],
                         post_process_list=[later_booster, median, average],
                         boost_target=3, outdir=tmpdirname)
    pout = dmp.pipeline(in_names, reject_value=2,
                        boost_amount=5)

# Prune outname ``None`` and remove directory
pruned_pout, pruned_in_names = prune_pout(pout, in_names)
pruned_outnames, pruned_meta = zip(*pruned_pout)
pruned_outnames = [os.path.basename(f) for f in pruned_outnames]
pruned_in_names = [os.path.basename(f) for f in pruned_in_names]
pretty_print = zip(pruned_in_names, pruned_outnames, pruned_meta)
print(list(pretty_print))

