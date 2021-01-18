This repository supports development of the BigMultiPipe project.

The primary product of the project is currently the bigmultipipe
Python module, which provides tools that enable a flexible, modular
approach to constructing data processing pipelines that optimize
computer processing, memory, and disk I/O resources.

As described in the package documentation at
https://bigmultipipe.readthedocs.io/en/latest/ the BigMultiPipe
package provides a framework for avoiding the limitations of Python's
Global Interpreter Lock (GIL) in the frequently encountered case where
analysis tasks on individual files can be performed independently and
thus in parallel.  BigMultiPipe goes a step further and provides tools
that handle the case where individual data files are large and, when
processed in parallel, could easily overwhelm computing and memory
resources.

Acknowledging bigmultipipe in your work

If you use bigmultipipe in work that leads to a publication, please
cite it in your references using this Zenodo link:
https://zenodo.org/badge/latestdoi/329778044

Thanks!

Acknowledgments

This module was developed with support from NSF grant AST-1616928 to
the Planetary Science Institute (https://psi.edu) and was started as
part of the Io Input/Output Observatory (IoIO) project hosted at
https://github.com/jpmorgen/IoIO
