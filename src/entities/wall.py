import os
import sys

from panda3d.core import CollisionNode
from panda3d.core import CollisionPolygon
from panda3d.core import Filename
from panda3d.core import Point3
from panda3d.physics import ActorNode

from src.physics import COLLIDE_MASK_INTO_WALL


# TODO: Factor out the information in this comment into a general Entity class.
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
class Wall(object):
    def __init__(self, app, pos, hpr):
        # TODO: Should we just pass these to avoid passing the app around?
        # cTrav = app.cTrav
        render = app.render

        # TODO: Factor this out.

        #   - self.rootNP
        #       - self.model
        #       - self.collisionNP
        #           - self.collisionGeom

        self.rootNP = render.attachNewNode(ActorNode("Wall"))
        self.rootNP.setPos(pos)
        self.rootNP.setHpr(hpr)

        self.model = loadModel(app, "green-square.egg")
        self.model.reparentTo(self.rootNP)

        self.collisionNP = self.rootNP.attachNewNode(
            CollisionNode("WallCollider")
        )
        self.collisionNP.node().setIntoCollideMask(COLLIDE_MASK_INTO_WALL)

        # For debugging purposes, uncomment the following line to show the
        # collision geometry.
        # self.collisionNP.show()

        # Note: I would have expected that a CollisionBox would be more robust
        # w/r/t glitching through it than a CollisionPolygon, since the latter
        # is infinitely thin and the former can have some thickness to it.
        # As an extreme example, I originally tried putting a 2x2x2 cube behind
        # each wall:
        #
        #     self.collisionGeom = CollisionBox(Point3(0, 0, -1), 1, 1, 1)
        #     self.collisionGeom = CollisionBox(Point3(-1, -1, -2.0),
        #                                       Point3( 1,  1,    0))
        #
        # But empirically, the CollisionBoxes are actually easier to glitch
        # through than a simple CollisionPolygon, so I use that instead.
        #
        # TODO: While the CollisionPolygon is pretty good at preventing the
        # player from glitching through, it usually doesn't seem to stop
        # bullets. Possibly we want something like this:
        #     https://www.panda3d.org/manual/index.php/
        #         Bullet_Continuous_Collision_Detection

        # The points for a CollisionPolygon go in counter-clockwise order.
        self.collisionGeom = CollisionPolygon(
            Point3( 1,  1, 0),
            Point3(-1,  1, 0),
            Point3(-1, -1, 0),
            Point3( 1, -1, 0),
        )
        self.collisionNP.node().addSolid(self.collisionGeom)


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

