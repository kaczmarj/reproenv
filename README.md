# ReproEnv

Generate Dockerfiles and Singularity recipes using templates. Available as a Python API.

# How to use it

1. Create template(s) to install software.
2. Register your template in reproenv

```python
import reproenv
reproenv.register(filepath='path/to/template.yaml')
```

3. Construct a Dockerfile or Singularity recipe with a Renderer object.

```python
import reproenv
dr = reproenv.DockerRenderer(pkg_manager='apt')
dr.from_('debian:stretch').run('echo "FOOBAR" > myfile.txt')
print(dr)

sr = reproenv.SingularityRenderer(pkg_manager='apt')
sr.from_('debian:stretch').run('echo "FOOBAR" > myfile.txt')
print(sr)

instructions = {
    'from_': 'debian:stretch',
    'run': 'echo "FOOBAR" > myfile.txt'}
dr = reproenv.DockerRenderer(pkg_manager='apt').from_dict(instructions)
print(dr)
sr = reproenv.SingularityRenderer(pkg_manager='apt').from_dict(instructions)
print(sr)
```

4. Build the Docker or Singularity image with the `docker` or `singularity` command-line tools. This part is out-of-scope for ReproEnv.

# Development

## Source tree

`/reproenv`
- `exceptions.py`: custom exception classes.
- `renderers.py`: objects to render Dockerfiles and Singularity files.
- `template.py`: objects and methods to handle templates, which describe how to install software packages.
- `types.py`: Python types and the ReproEnv schema. Templates are validated against the `_template_schema` object in this file, and dictionaries passed to `*Renderer` objects are validated against the `_renderer_schema` object in this file.
- `utils.py`: utility functions for the package.

## Glossary

- renderer: a Python object defined in ReproEnv that constructs a Dockerfile or Singularity recipe. These objects follow a common API, despite generating different container specifications.
- template: a dictionary that specifies how to install a particular software package. A template includes instructions for installing pre-compiled binaries and/or from source. Each installation method includes required dependencies to be installed using the system package manager, bash commands to install the software (e.g., cloning a git repository and building, or downloading pre-compiled binaries).
