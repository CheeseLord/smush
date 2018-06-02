import os
import sys

from panda3d.core import CollisionNode
from panda3d.core import CollisionPlane
from panda3d.core import CollisionSphere
from panda3d.core import Filename
from panda3d.core import Plane
from panda3d.core import Point3
from panda3d.core import Vec3
from panda3d.physics import ActorNode

from src import graphics # TODO[#2]
from src import physics  # TODO[#2]

from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_INTO_FLOOR   # TODO[#2]
from src.physics import COLLIDE_MASK_INTO_PLAYER  # TODO[#2]
from src.physics import COLLIDE_MASK_INTO_WALL    # TODO[#2]
from src.world_config import PLAYER_HEIGHT

MIN_X =  -7
MAX_X =   7
MIN_Y = -13
MAX_Y =  13

log = newLogger(__name__)

app = None

def initWorld(app_):
    """
    Make sure all the things that are supposed to exist are created and
    loaded appropriately.
    """

    global app
    app = app_

    # TODO: Magic numbers bad (position and scale)
    # scene = loadExampleModel("environment")
    # scene.reparentTo(app.render)
    # scene.setScale(0.25, 0.25, 0.25)
    # scene.setPos(-8, 42, 0)

    # TODO: Magic numbers bad (hardcoded based on the squares being 2x2).

    # Floor
    for x in range(MIN_X, MAX_X+1, 2):
        for y in range(MIN_Y, MAX_Y+1, 2):
            floorTile = loadModel("red-square.egg")
            floorTile.reparentTo(app.render)
            floorTile.setPos(x, y, 0)

    # North wall
    for x in range(MIN_X, MAX_X+1, 2):
        wallTile = loadModel("green-square.egg")
        wallTile.reparentTo(app.render)
        # TODO: Make the models [0,1]x[0,1]
        wallTile.setPos(x, MAX_Y+1, 1)
        wallTile.setHpr(0, 90, 0)

    # South wall
    for x in range(MIN_X, MAX_X+1, 2):
        wallTile = loadModel("green-square.egg")
        wallTile.reparentTo(app.render)
        wallTile.setPos(x, MIN_Y-1, 1)
        wallTile.setHpr(0, 90, 180)

    # West wall
    for y in range(MIN_Y, MAX_Y+1, 2):
        wallTile = loadModel("green-square.egg")
        wallTile.reparentTo(app.render)
        wallTile.setPos(MIN_X-1, y, 1)
        wallTile.setHpr(0, 90, 90)

    # East wall
    for y in range(MIN_Y, MAX_Y+1, 2):
        wallTile = loadModel("green-square.egg")
        wallTile.reparentTo(app.render)
        wallTile.setPos(MAX_X+1, y, 1)
        wallTile.setHpr(0, 90, -90)

    # For testing orientations
    #
    # rect1 = loadModel("green-square.egg")
    # rect1.reparentTo(app.render)
    # rect1.setPos(2, 0, 1.5)
    # rect1.setHpr(0, 0, 0)
    #
    # rect2 = loadModel("green-square.egg")
    # rect2.reparentTo(app.render)
    # rect2.setPos(4, 0, 1.5)
    # rect2.setHpr(135, 0, 0)
    #
    # rect3 = loadModel("green-square.egg")
    # rect3.reparentTo(app.render)
    # rect3.setPos(6, 0, 1.5)
    # rect3.setHpr(0, 135, 0)
    #
    # rect4 = loadModel("green-square.egg")
    # rect4.reparentTo(app.render)
    # rect4.setPos(8, 0, 1.5)
    # rect4.setHpr(0, 0, 135)

    # Add collision geometry for the ground. For now, it's just an infinite
    # plane; eventually we should figure out how to actually match it with
    # the environment model.
    groundCollider = app.render.attachNewNode(
        CollisionNode("groundCollider")
    )
    groundCollider.node().setIntoCollideMask(
        COLLIDE_MASK_INTO_FLOOR
    )
    # The collision solid must be added to the node, not the NodePath.
    groundCollider.node().addSolid(
        CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, 0)))
    )

    # A floating spherical object which can be toggled between a smiley and
    # a frowney. Called the smiley for historical reasons.
    graphics.smileyNP = app.render.attachNewNode("SmileyNP")
    # Lift the smiley/frowney up a bit so that if the player runs into it,
    # it'll try to push them down. This used to demonstrate a bug where the
    # ground didn't push back and so the player would just be pushed
    # underground. At this point it's just for historical reasons.
    graphics.smileyNP.setPos(-5, 10, 1.25)

    graphics.smileyModel = loadExampleModel("smiley")
    graphics.smileyModel.reparentTo(graphics.smileyNP)
    graphics.frowneyModel = loadExampleModel("frowney")

    smileyCollide = graphics.smileyNP.attachNewNode(
        CollisionNode("SmileyCollide")
    )
    # The smiley is logically a wall, so set its into collision mask as
    # such.
    smileyCollide.node().setIntoCollideMask(COLLIDE_MASK_INTO_WALL)
    smileyCollide.node().addSolid(CollisionSphere(0, 0, 0, 1))

    # TODO[#2]: Functions in graphics.py to set pos and hpr.
    # TODO[#2]: ...what about the physics code in control.py?
    # playerNP is at the player's feet, not their center of mass.
    graphics.playerNP = app.render.attachNewNode(ActorNode("Player"))
    graphics.playerNP.setPos(0, 0, 0)
    app.physicsMgr.attachPhysicalNode(graphics.playerNP.node())
    graphics.playerHeadNP = graphics.playerNP.attachNewNode("PlayerHead")
    # Put the player's head a little below the actual top of the player so
    # that if you're standing right under an object, the object is still
    # within your camera's viewing frustum.
    graphics.playerHeadNP.setPos(0, 0, PLAYER_HEIGHT - 0.2)
    app.camera.reparentTo(graphics.playerHeadNP)
    # Move the camera's near plane closer than the default (1) so that when
    # the player butts their head against a wall, they don't see through
    # it. In general, this distance should be close enough that the near
    # plane stays within the player's hitbox (even as the player's head
    # rotates in place). For more on camera/lens geometry in Panda3D, see:
    #     https://www.panda3d.org/manual/index.php/Lenses_and_Field_of_View
    app.camLens.setNear(0.1)

    # For colliding the player with walls, floor, and other such obstacles.
    playerCollider = graphics.playerNP.attachNewNode(
        CollisionNode("playerCollider")
    )
    playerCollider.node().setIntoCollideMask(COLLIDE_MASK_INTO_PLAYER)
    playerCollider.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
                                             COLLIDE_MASK_INTO_WALL)
    playerCollider.node().addSolid(
        CollisionSphere(0, 0, 0.5 * PLAYER_HEIGHT, 0.5 * PLAYER_HEIGHT)
    )

    physics.physicsCollisionHandler.addCollider(playerCollider,
                                                graphics.playerNP)
    app.cTrav.addCollider(playerCollider, physics.physicsCollisionHandler)


def loadModel(modelName):
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

def loadExampleModel(modelName):
    return app.loader.loadModel(modelName)

