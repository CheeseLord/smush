import os
import sys

from panda3d.bullet import BulletCharacterControllerNode
from panda3d.bullet import BulletPlaneShape
from panda3d.bullet import BulletRigidBodyNode
from panda3d.bullet import BulletSphereShape
from panda3d.core import AmbientLight
from panda3d.core import Filename
from panda3d.core import Point3
from panda3d.core import PointLight
from panda3d.core import VBase4
from panda3d.core import Vec3

from src import graphics # TODO[#2]
from src import physics  # TODO[#2]

from src.entities.panel import Floor
from src.entities.panel import Wall
from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_GROUND_PLANE
from src.physics import COLLIDE_MASK_PLAYER
from src.physics import COLLIDE_MASK_SCENERY
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

    # TODO[bullet]: Factor out all the logic below that creates objects.

    # Greg 2018-07-07 -- Temporarily add a half-cube of walls and floor to
    # demonstrate that the physics are weird at corners.
    # FIXME[bullet]: This doesn't seem to work anymore.
    # Probably we'd need to recreate it without reparenting the bullet-physics
    # nodes below other nodes.
    #
    # halfCubeNP = app.render.attachNewNode("HalfCubeNP")
    # Floor(app, Point3(0, 0, 0), (0,  0,  0), 1, 1, parent=halfCubeNP)
    # Wall(app, Point3(0, 0, 0), (0, 90,  90), 1, 1, parent=halfCubeNP)
    # Wall(app, Point3(1, 0, 0), (0, 90, 180), 1, 1, parent=halfCubeNP)
    # halfCubeNP.setPos(3, 20, 0)
    # halfCubeNP.setHpr(180, 5, -5)

    # Add an invisible collision plane below the floor (z=-1) so that if the
    # player glitches past the floor somehow, they at least don't fall forever
    # into the bottomless abyss.
    groundShape = BulletPlaneShape(Vec3(0, 0, 1), 0)
    groundNode = BulletRigidBodyNode("Ground")
    groundNode.addShape(groundShape)
    groundNP = app.render.attachNewNode(groundNode)
    groundNP.setPos(0, 0, -1)
    groundNP.setCollideMask(COLLIDE_MASK_GROUND_PLANE)
    physics.world.attachRigidBody(groundNode)

    # A floating spherical object which can be toggled between a smiley and
    # a frowney. Called the smiley for historical reasons.
    smileyShape = BulletSphereShape(1.0)
    smileyNode = BulletRigidBodyNode("Smiley")
    smileyNode.addShape(smileyShape)

    graphics.smileyNP = app.render.attachNewNode(smileyNode)
    # Lift the smiley/frowney up a bit so that if the player runs into it,
    # it'll try to push them down. This used to demonstrate a bug where the
    # ground didn't push back and so the player would just be pushed
    # underground. At this point it's just for historical reasons.
    graphics.smileyNP.setPos(-5, 10, 1.25)
    graphics.smileyNP.setCollideMask(COLLIDE_MASK_SCENERY)
    physics.world.attachRigidBody(smileyNode)

    graphics.smileyModel = loadExampleModel("smiley")
    graphics.smileyModel.reparentTo(graphics.smileyNP)
    graphics.frowneyModel = loadExampleModel("frowney")

    playerShape = BulletSphereShape(0.5 * PLAYER_HEIGHT)
    # Second param is step_height.
    player = BulletCharacterControllerNode(playerShape, 0.2, "Player")
    player.setMaxSlope(45.0)
    # The example code does this, but I don't think it has any effect? Seems
    # like the player defaults to the world gravity if it's not otherwise
    # specified.
    # player.setGravity(9.81)

    # TODO[#2][bullet]: Why does graphics own playerNP?!
    # TODO[#2]: Functions in graphics.py to set pos and hpr.
    # TODO[#2]: ...what about the physics code in control.py?
    graphics.playerNP = app.render.attachNewNode(player)
    graphics.playerNP.setPos(0, 0, 1)
    graphics.playerNP.setCollideMask(COLLIDE_MASK_PLAYER)
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

