import sys

from direct.showbase.ShowBase import ShowBase
from panda3d.core import CollisionHandlerEvent
from panda3d.core import CollisionNode
from panda3d.core import CollisionPlane
from panda3d.core import CollisionSphere
from panda3d.core import CollisionTraverser
from panda3d.core import Plane
from panda3d.core import Point3
from panda3d.core import Vec3
from panda3d.core import WindowProperties
from panda3d.physics import ActorNode
from panda3d.physics import ForceNode
from panda3d.physics import LinearVectorForce
from panda3d.physics import PhysicsCollisionHandler

from src.control import clicked
from src.control import controlCameraTask
from src.control import movePlayerTask
from src.logconfig import enableDebugLogging
from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_INTO_FLOOR
from src.physics import COLLIDE_MASK_INTO_PLAYER
from src.physics import COLLIDE_MASK_INTO_WALL
from src.physics import onCollideEventIn
from src.physics import onCollideEventOut
from src.world_config import GRAVITY_ACCEL
from src.world_config import PLAYER_HEIGHT

log = newLogger(__name__)

LOG_DEBUG = False

# TODO: figure out something re: pylint and nonconstant globals
app = None # pylint: disable=invalid-name

def main():
    log.info("Begin.")

    if LOG_DEBUG:
        enableDebugLogging()
        log.info("Debug logging enabled.")
        log.debug("Debug logging enabled.")
    else:
        log.info("Debug logging disabled.")

    # Why does 'global x' cause pylint to assume x is a constant? If I wanted
    # to use x as a constant I'd just reference it; I wouldn't go to the
    # trouble of adding a declaration that allows me to write to it.
    global app # pylint: disable=invalid-name
    app = MyApp()
    app.run()

    # Not reached; I think Panda3D calls sys.exit when you close the window.
    log.info("End.")

class MyApp(ShowBase):

    ###########################################################################
    # Initialization

    def __init__(self):
        ShowBase.__init__(self)

        # This is available as a global, but pylint gives an undefined-variable
        # warning if we use it that way. Looking at
        #     https://www.panda3d.org/manual/index.php/ShowBase
        # I would have thought we could reference it as either
        # self.globalClock, direct.showbase.ShowBase.globalClock, or possibly
        # direct.showbase.globalClock, but none of those seems to work. In
        # WaRTS, we got around this by creating it here (using
        # ClockObject.getGlobalClock()), but now pylint complains about even
        # that because it doesn't think the name ClockObject is present in
        # panda3d.core. Since we're going to have to suppress a pylint warning
        # anyway, just read the global here into an instance variable, so we
        # can suppress one undefined-variable here and then just use
        # self.globalClock everywhere else.
        self.globalClock = globalClock # pylint: disable=undefined-variable

        # How many previous frames have we successfully warped the mouse? Only
        # tracked up to FRAMES_NEEDED_TO_WARP.
        # I would have initialized this in self.initKeyboardAndMouse, but
        # pylint doesn't like attribute-defined-outside-init. Actually, I'm not
        # entirely sure why it doesn't complain about all the other attributes
        # we define outside of init. Maybe it has something to do with this?
        #     https://github.com/PyCQA/pylint/issues/192
        # Specifically the comment:
        #     "Don't emit 'attribute-defined-outside-init' if the attribute was
        #     set by a function call in a defining method."
        self.successfulMouseWarps = 0

        # This is just here to satisfy pylint's attribute-defined-outside-init.
        self.smileyIsFrowney = False

        self.initPhysics()
        self.initCollisionHandling()
        self.initObjects()
        self.initPlayer()
        self.initKeyboardAndMouse()

    def initPhysics(self):
        # Start the physics (yes, with the particle engine).
        self.enableParticles()
        gravityNode = ForceNode("world-forces")
        gravityForce = LinearVectorForce(0, 0, -GRAVITY_ACCEL)
        gravityNode.addForce(gravityForce)
        self.physicsMgr.addLinearForce(gravityForce)

    def initCollisionHandling(self):
        """
        Initialize the collision handlers. This must be run before any objects
        are created.
        """

        self.cTrav = CollisionTraverser()

        # Used to handle collisions between physics-affected objects.
        self.physicsCollisionHandler = PhysicsCollisionHandler()

        # Used to run custom code on collisions.
        self.eventCollisionHandler = CollisionHandlerEvent()

        self.eventCollisionHandler.addInPattern("%fn-into-%in")
        self.eventCollisionHandler.addOutPattern("%fn-out-%in")

        self.accept("BulletColliderEvt-into-SmileyCollide",
                    onCollideEventIn)
        self.accept("BulletColliderEvt-out-SmileyCollide",
                    onCollideEventOut)

    def initObjects(self):
        """
        Initialize all the objects that are initially in the world. Set up
        their geometry (position, orientation, scaling) and create collision
        geometry for them as appropriate. (Therefore, initCollisionHandling
        must be called before this function.) Load them all into the scene
        graph.
        """

        # Load the environment model.
        # TODO: Magic numbers bad (position and scale)
        self.scene = self.loader.loadModel("models/environment")
        self.scene.reparentTo(self.render)
        self.scene.setScale(0.25, 0.25, 0.25)
        self.scene.setPos(-8, 42, 0)

        # Add collision geometry for the ground. For now, it's just an infinite
        # plane; eventually we should figure out how to actually match it with
        # the environment model.
        self.groundCollider = self.render.attachNewNode(
            CollisionNode("groundCollider")
        )
        self.groundCollider.node().setIntoCollideMask(
            COLLIDE_MASK_INTO_FLOOR
        )
        # The collision solid must be added to the node, not the NodePath.
        self.groundCollider.node().addSolid(
            CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, 0)))
        )

        # A floating spherical object which can be toggled between a smiley and
        # a frowney. Called the smiley for historical reasons.
        self.smileyNP = self.render.attachNewNode("SmileyNP")
        # Lift the smiley/frowney up a bit so that if the player runs into it,
        # it'll try to push them down. This used to demonstrate a bug where the
        # ground didn't push back and so the player would just be pushed
        # underground. At this point it's just for historical reasons.
        self.smileyNP.setPos(-5, 10, 1.25)

        self.smileyModel = self.loader.loadModel("smiley")
        self.smileyModel.reparentTo(self.smileyNP)
        self.frowneyModel = self.loader.loadModel("frowney")
        self.smileyIsFrowney = False

        self.smileyCollide = self.smileyNP.attachNewNode(
            CollisionNode("SmileyCollide")
        )
        # The smiley is logically a wall, so set its into collision mask as
        # such.
        self.smileyCollide.node().setIntoCollideMask(COLLIDE_MASK_INTO_WALL)
        self.smileyCollide.node().addSolid(CollisionSphere(0, 0, 0, 1))

    def initPlayer(self):
        # playerNP is at the player's feet, not their center of mass.
        self.playerNP = self.render.attachNewNode(ActorNode("Player"))
        self.playerNP.setPos(0, 0, 0)
        self.physicsMgr.attachPhysicalNode(self.playerNP.node())
        self.playerHeadNP = self.playerNP.attachNewNode("PlayerHead")
        # Put the player's head a little below the actual top of the player so
        # that if you're standing right under an object, the object is still
        # within your camera's viewing frustum.
        self.playerHeadNP.setPos(0, 0, PLAYER_HEIGHT - 0.2)
        self.camera.reparentTo(self.playerHeadNP)
        # Move the camera's near plane closer than the default (1) so that when
        # the player butts their head against a wall, they don't see through
        # it. In general, this distance should be close enough that the near
        # plane stays within the player's hitbox (even as the player's head
        # rotates in place). For more on camera/lens geometry in Panda3D, see:
        #     https://www.panda3d.org/manual/index.php/Lenses_and_Field_of_View
        self.camLens.setNear(0.1)

        # For colliding the player with walls, floor, and other such obstacles.
        self.playerCollider = self.playerNP.attachNewNode(
            CollisionNode("playerCollider")
        )
        self.playerCollider.node().setIntoCollideMask(COLLIDE_MASK_INTO_PLAYER)
        self.playerCollider.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
                                                      COLLIDE_MASK_INTO_WALL)
        self.playerCollider.node().addSolid(
            CollisionSphere(0, 0, 0.5 * PLAYER_HEIGHT, 0.5 * PLAYER_HEIGHT)
        )

        self.physicsCollisionHandler.addCollider(self.playerCollider,
                                                 self.playerNP)
        self.cTrav.addCollider(self.playerCollider,
                               self.physicsCollisionHandler)

    def initKeyboardAndMouse(self):
        # Hide the mouse.
        self.disableMouse()
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)

        # Provide a way to exit even when we make the window fullscreen.
        self.accept('control-q', sys.exit)

        # Handle the mouse.
        self.accept("mouse1", clicked, [])

        # Camera toggle.
        # self.accept("f3",       self.toggleCameraStyle, [])

        # Handle window close request (clicking the X, Alt-F4, etc.)
        # self.win.set_close_request_event("window-close")
        # self.accept("window-close", self.handleWindowClose)

        self.taskMgr.add(controlCameraTask, "ControlCameraTask")
        self.taskMgr.add(movePlayerTask,    "MovePlayerTask")


if __name__ == "__main__":
    main()

