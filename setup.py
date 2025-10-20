from setuptools import setup, Extension
from Cython.Build import cythonize
from pathlib import Path

extensions = [
    Extension(
        "game.server.game_logic.services.fast_copy",
        ["game/server/game_logic/services/fast_copy.pyx"],
    )
]

setup(
    name='Brass Performer',
    ext_modules=cythonize(extensions)
)