Contributing
============

Thank you for your interest in contributing to *SDU Agro Tools* and we welcome all pull request. To get set for development on *SDU Agro Tools* see the following.

Development uses uv and pre-commit for code linting and formatting. To setup development with uv and pre-commit follow these steps after cloning the repository:

Let uv create a virtual environment:

.. code-block:: shell

    uv sync --all-extras

Install pre-commit hooks

.. code-block:: shell

    uv run pre-commit install

You are now ready to contribute.

Generating Documentation
------------------------

To generate this documentation, in the *docs* folder run:

.. code-block:: shell

    uv run make html

This will generate html documentation in the *docs/build/html* folder.

Creating Github Release
-----------------------

When a new release is desired from the commits to the master branch, the following steps will create a new release and bump the version number:

* Change version number in :code:`src/sdu_agro_tools/metadata.txt` and commit to main.
* Tag the commit with the version number: :code:`git tag vXX.XX.XX`.
* Push the changes to github: :code:`git push origin` (where origin is the name of github upstream).
* push the tag to github: :code:`git push origin tag vXX.XX.XX`.

This will start the github actions to create a new release and publish the code to PyPI together with generating the new documentation.
