import os
import sys

from panda3d.core import Filename


# TODO: Factor out the stuff that could belong to general entities.
class Wall(object):
    def __init__(self, app, pos, hpr):
        # TODO: Should we just pass these to avoid pasing the app around?
        # cTrav = app.cTrav
        render = app.render

        # TODO: Factor this out.
        tile = loadModel(app, "green-square.egg")
        tile.reparentTo(render)
        tile.setPos(pos)
        tile.setHpr(hpr)


# FIXME: Factor this out.
def loadModel(app, modelName):
    """
    Load and return a Panda3D model given a path. The modelName is relative to
    the repo's assets/models directory.
    """

    # Instructions for loading models at:
    #    https://www.panda3d.org/manual/index.php/Loading_Models

    repository = os.path.abspath(sys.path[0])
    repository = Filename.fromOsSpecific(repository).getFullpath()
    if not repository.endswith('/'):
        repository += '/'
    modelsDir = repository + 'assets/models/'

    return app.loader.loadModel(modelsDir + modelName)

