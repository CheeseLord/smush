from panda3d.core import CollisionNode
from panda3d.core import CollisionPlane
from panda3d.core import CollisionSphere
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
    scene = app.loader.loadModel("models/environment")
    scene.reparentTo(app.render)
    scene.setScale(0.25, 0.25, 0.25)
    scene.setPos(-8, 42, 0)

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

    graphics.smileyModel = app.loader.loadModel("smiley")
    graphics.smileyModel.reparentTo(graphics.smileyNP)
    graphics.frowneyModel = app.loader.loadModel("frowney")

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

