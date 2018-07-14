import os
import sys

from panda3d.bullet import BulletCharacterControllerNode
from panda3d.bullet import BulletSphereShape
from panda3d.core import AmbientLight
from panda3d.core import CollisionNode
from panda3d.core import CollisionPlane
from panda3d.core import CollisionSphere
from panda3d.core import Filename
from panda3d.core import Plane
from panda3d.core import Point3
from panda3d.core import PointLight
from panda3d.core import VBase4
from panda3d.core import Vec3
# from panda3d.physics import ActorNode

from src import graphics # TODO[#2]
from src import physics  # TODO[#2]

from src.entities.panel import Floor
from src.entities.panel import Wall
from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_INTO_FLOOR   # TODO[#2]
# from src.physics import COLLIDE_MASK_INTO_PLAYER  # TODO[#2]
from src.physics import COLLIDE_MASK_INTO_WALL    # TODO[#2]
from src.world_config import PLAYER_HEIGHT

MIN_X =  -8
MAX_X =   8
MIN_Y = -14
MAX_Y =  14

log = newLogger(__name__)

app = None

def initWorld(app_):
    """
    Make sure all the things that are supposed to exist are created and
    loaded appropriately.
    """

    global app
    app = app_

    # FIXME this is probably a horrrible idea but
    # enable shader generation for the entire game
    app.render.setShaderAuto()

    # TODO: Magic numbers bad (lighting parameters)
    # ambient lighting
    ambientLight = AmbientLight("ambientLight")
    ambientLight.setColor(VBase4(0.1, 0.1, 0.1, 1))
    ambientLightNP = app.render.attachNewNode(ambientLight)
    app.render.setLight(ambientLightNP)

    # point lighting
    pointLight = PointLight("pointLight")
    pointLight.setColor(VBase4(0.8, 0.8, 0.8, 1))
    # Use a 512 x 512 resolution shadow map
    pointLight.setShadowCaster(True, 512, 512)
    pointLightNP = app.render.attachNewNode(pointLight)
    pointLightNP.setPos(0,0,30)
    app.render.setLight(pointLightNP)

    # Define the floor and walls.
    # TODO: Keep track of these objects?

    Floor(app, Point3(MIN_X, MIN_Y, 0), (0, 0, 0),
          (MAX_X - MIN_X), (MAX_Y - MIN_Y))

    # North wall
    Wall(app, Point3(MIN_X, MAX_Y, 0), (0, 90,   0), (MAX_X - MIN_X), 2)
    # South wall
    Wall(app, Point3(MAX_X, MIN_Y, 0), (0, 90, 180), (MAX_X - MIN_X), 2)
    # West wall
    Wall(app, Point3(MIN_X, MIN_Y, 0), (0, 90,  90), (MAX_Y - MIN_Y), 2)
    # East wall
    Wall(app, Point3(MAX_X, MAX_Y, 0), (0, 90, -90), (MAX_Y - MIN_Y), 2)

    # Greg 2018-07-07 -- Temporarily add a half-cube of walls and floor to
    # demonstrate that the physics are weird at corners.
    # FIXME[bullet]: This doesn't seem to work anymore.
    # halfCubeNP = app.render.attachNewNode("HalfCubeNP")
    # Floor(app, Point3(0, 0, 0), (0,  0,  0), 1, 1, parent=halfCubeNP)
    # Wall(app, Point3(0, 0, 0), (0, 90,  90), 1, 1, parent=halfCubeNP)
    # Wall(app, Point3(1, 0, 0), (0, 90, 180), 1, 1, parent=halfCubeNP)
    # halfCubeNP.setPos(3, 20, 0)
    # halfCubeNP.setHpr(180, 5, -5)

    # Add collision geometry for the ground. For now, it's just an infinite
    # plane; eventually we should figure out how to actually match it with
    # the environment model. Put it at z=-1 so that we can tell if something
    # clips through the actual floor, which is at z=0.
    groundCollider = app.render.attachNewNode(
        CollisionNode("groundCollider")
    )
    groundCollider.node().setIntoCollideMask(
        COLLIDE_MASK_INTO_FLOOR
    )
    # The collision solid must be added to the node, not the NodePath.
    groundCollider.node().addSolid(
        CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, -1)))
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

    playerShape = BulletSphereShape(0.5 * PLAYER_HEIGHT)
    # Second param is step_height.
    player = BulletCharacterControllerNode(playerShape, 0.2, "Player")
    player.setMaxSlope(45.0)
    # The example did this, but I don't think it has any effect? Seems like the
    # player defaults to the world gravity if it's not otherwise specified.
    # player.setGravity(9.81)

    # # playerNP is at the player's feet, not their center of mass.
    # graphics.playerNP = app.render.attachNewNode(ActorNode("Player"))
    # graphics.playerNP.setPos(0, 0, 0)
    # app.physicsMgr.attachPhysicalNode(graphics.playerNP.node())
    # graphics.playerHeadNP = graphics.playerNP.attachNewNode("PlayerHead")

    # TODO[#2][bullet]: Why does graphics own playerNP?!
    # TODO[#2]: Functions in graphics.py to set pos and hpr.
    # TODO[#2]: ...what about the physics code in control.py?
    graphics.playerNP = app.render.attachNewNode(player)
    graphics.playerNP.setPos(0, 0, 1)
    physics.world.attachCharacter(player)
    graphics.playerHeadNP = graphics.playerNP.attachNewNode("PlayerHead")

    # Put the player's head a little below the actual top of the player so
    # that if you're standing right under an object, the object is still
    # within your camera's viewing frustum.
    graphics.playerHeadNP.setPos(0, 0, 0.3 * PLAYER_HEIGHT)
    app.camera.reparentTo(graphics.playerHeadNP)
    # Move the camera's near plane closer than the default (1) so that when
    # the player butts their head against a wall, they don't see through
    # it. In general, this distance should be close enough that the near
    # plane stays within the player's hitbox (even as the player's head
    # rotates in place). For more on camera/lens geometry in Panda3D, see:
    #     https://www.panda3d.org/manual/index.php/Lenses_and_Field_of_View
    app.camLens.setNear(0.1)

    # # For colliding the player with walls, floor, and other such obstacles.
    # playerCollider = graphics.playerNP.attachNewNode(
    #     CollisionNode("playerCollider")
    # )
    # playerCollider.node().setIntoCollideMask(COLLIDE_MASK_INTO_PLAYER)
    # playerCollider.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
    #                                          COLLIDE_MASK_INTO_WALL)
    # playerCollider.node().addSolid(
    #     CollisionSphere(0, 0, 0.5 * PLAYER_HEIGHT, 0.5 * PLAYER_HEIGHT)
    # )

    # physics.physicsCollisionHandler.addCollider(playerCollider,
    #                                             graphics.playerNP)
    # app.cTrav.addCollider(playerCollider, physics.physicsCollisionHandler)


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

