import os
import sys

from panda3d.bullet import BulletRigidBodyNode
from panda3d.bullet import BulletTriangleMesh
from panda3d.bullet import BulletTriangleMeshShape
from panda3d.core import Filename
from panda3d.core import Point3
from panda3d.core import Texture
from panda3d.core import TextureStage

from src.physics import COLLIDE_MASK_SCENERY

# FIXME[bullet]
from src import physics


# TODO: Factor out the information in this comment into a general Entity class.
#
# FIXME[bullet]: This structure may be wrong now that we're using bullet.
#
# Typical structure of entity with model and collision geometry:
#
#   - Root NodePath for entity (an ActorNode if entity is subject to physics)
#       - Model
#       - CollisionNodePath
#           - CollisionGeometry
#
# So you would do something like:
#
#     entityNP = render.attachNewNode(ActorNode("EntityName"))
#
#     # Model
#     entityModel = loadModel("modelName")
#     entityModel.reparentTo(entityNP)
#
#     # Collision node/geometry
#     entityCollisionNP = entityNP.attachNewNode(CollisionNode("ColNodeName"))
#     entityCollisionNP.node().setIntoCollideMask(...)
#     entityCollisionNP.node().setFromCollideMask(...) # For "from" colliders
#     entityCollisionGeometry = CollisionSphere(0, 0, 0, 1)
#     entityCollisionNP.node().addSolid(entityCollisionGeometry)
#
#     # Setup collision handling
#     physicsCollisionHandler.addCollider(entityCollisionNP, entityNP)
#     app.cTrav.addCollider(entityCollisionNP, physicsCollisionHandler)


# TODO: Factor out the stuff that could belong to general entities.
class Panel(object):
    # TODO: "width" and "height" aren't the best names here. They're really the
    # dimensions in the x and y directions, but "height" sounds like the z
    # direction.
    def __init__(self, app, pos, hpr, width, height, textureName, parent=None):
        """
        Create a (width x height) wall, with its bottom-left corner at pos,
        rotated according to hpr. The wall's texture will be tiled
        appropriately.
        """

        super(Panel, self).__init__()

        # TODO: Should we just pass these to avoid passing the app around?
        # cTrav = app.cTrav
        if parent is None:
            parent = app.render

        # TODO: Factor this out.

        # FIXME[bullet]
        #   - self.rootNP
        #       - self.model
        #       - self.collisionNP
        #           - self.collisionGeom

        bl = Point3(0,     0,      0)
        br = Point3(width, 0,      0)
        tr = Point3(width, height, 0)
        tl = Point3(0,     height, 0)
        mesh = BulletTriangleMesh()
        mesh.addTriangle(bl, tl, br)
        mesh.addTriangle(tl, br, tr)
        # TODO: Comment about merits of TriangleMesh vs. Box.
        shape = BulletTriangleMeshShape(mesh, dynamic=False)

        node = BulletRigidBodyNode("Panel")
        node.addShape(shape)

        self.rootNP = parent.attachNewNode(node)
        self.rootNP.setPos(pos)
        self.rootNP.setHpr(hpr)
        self.rootNP.setCollideMask(COLLIDE_MASK_SCENERY)

        physics.world.attachRigidBody(node)

        self.model = loadModel(app, "unit-tile-notex.egg")
        self.model.reparentTo(self.rootNP)

        self.texStage = getTextureStage("WallTextureStage")

        self.texture = loadTexture(app, textureName)
        # When the model is larger than the texture, cover it by tiling the
        # texture.
        self.texture.setWrapU(Texture.WM_repeat)
        self.texture.setWrapV(Texture.WM_repeat)
        # Note: extrapolating from:
        #     https://www.panda3d.org/manual/index.php/
        #         Simple_Texture_Replacement
        # I believe the last parameter is "override". (I couldn't find this in
        # the API reference.) Set it to 1 just in case the model already has a
        # texture, though it's not supposed to.
        self.model.setTexture(self.texStage, self.texture, 1)

        # Scale the texture's UV coordinates by the same amount we scale the
        # model, so that the texture will be used for a 1x1 region.
        self.model.setScale(width, height, 1)
        self.model.setTexScale(self.texStage, width, height)


class Wall(Panel):
    def __init__(self, app, pos, hpr, width, height, **kwargs):
        super(Wall, self).__init__(app, pos, hpr, width, height,
                                   "green-square.png", **kwargs)

class Floor(Panel):
    def __init__(self, app, pos, hpr, width, height, **kwargs):
        super(Floor, self).__init__(app, pos, hpr, width, height,
                                    "red-square.png", **kwargs)


# FIXME: This is a hack to work around what might be a bug with the default
# shaders? I'm not really sure what's going on.
#
# If we create 4 walls with different texture scales but with the textures
# coming from the same file and all using a single TextureStage, then
# empirically the walls glitch between the different texture scalings.
#
# As far as I can tell, the above is supposed to work (i.e., there shouldn't be
# glitching). For example:
#     "Each TextureStage can hold one texture image for a particular model. If
#     you assign a texture to a particular TextureStage, and then later (or at
#     a lower node) assign a different texture to the same TextureStage, the
#     new texture completely replaces the old one. (Within the overall scene, a
#     given TextureStage can be used to hold any number of different textures
#     for different nodes; but it only holds one texture for any one particular
#     node.)"
# from:
#     https://www.panda3d.org/manual/index.php/Multitexture_Introduction
# Meaning we should be fine to use a single TextureStage for all of them (say,
# the default TextureStage).
#
# Also, I'm not sure whether loading a single file twice as a texture gives you
# a single texture or two distinct-but-identical textures, but even if they're
# the same, it should be fine to set the TexScale differently, since it doesn't
# actually modify the texture:
#     "Note that the operation in each case is applied to the (u, v) texture
#     coordinates, not to the texture; so it will have the opposite effect on
#     the texture."
# from:
#     https://www.panda3d.org/manual/index.php/Texture_Transforms
#
# Some workarounds that empirically fix the problem:
#   - Using a different TextureStage for each wall, and giving all the
#     TextureStages different names.
#       - But using different TextureStages with the same name does not fix the
#         problem!
#   - Loading the textures for different walls from different files (even if
#     they're identical images).
#   - Removing the following line from initWorld:
#         app.render.setShaderAuto()
#
# This function is a helper for implementing the first of the above
# workarounds.
#
# Note that the third workaround suggests that maybe the problem is in the
# default shaders, so a better(?) possibility might be to write our own
# shaders.
numTextureStages = 0
def getTextureStage(baseName=None):
    global numTextureStages
    if baseName is None:
        prefix = ""
    else:
        prefix = baseName + "-"
    # Note: you can always recover the numTextureStages from the name of a
    # TextureStage as follows:
    #     If the name contains "-", take everything after the last "-".
    #     Otherwise, take the whole name.
    # Therefore, no matter what inputs we get for the baseName, every
    # TextureStage returned by this function will have a unique name.
    texStage = TextureStage(prefix + str(numTextureStages))
    numTextureStages += 1
    return texStage

# FIXME: Factor these out.
# FIXME: Refactor w/ each other as well.
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

def loadTexture(app, textureName):
    """
    Load and return a Panda3D model given a path. The textureName is relative
    to the repo's assets/models/tex directory.
    """

    repository = os.path.abspath(sys.path[0])
    repository = Filename.fromOsSpecific(repository).getFullpath()
    if not repository.endswith('/'):
        repository += '/'
    textureDir = repository + 'assets/models/tex/'

    return app.loader.loadTexture(textureDir + textureName)

