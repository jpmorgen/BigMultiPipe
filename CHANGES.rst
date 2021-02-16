0.1.0
=====

Improve pre_process_list and post_process_list function usability.
Now allows data or ``None`` to be return unless the pre-process
control or post-process metadata features are needed, In that case,
``dict`` are returned with appropriate keys: ``bmp_data`` and
``bpm_kwargs`` for pre-process routines, ``bmp_data`` and ``bpm_meta``
for post-process routines.

0.0.x
=====

Initial release.  Proof of principle
