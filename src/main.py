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
from panda3d.physics import PhysicsCollisionHandler

from src import graphics # TODO[#2]
from src import physics  # TODO[#2]

from src.control import clicked
from src.control import controlCameraTask
from src.control import initControl
from src.control import movePlayerTask
from src.graphics import initGraphics
from src.logconfig import enableDebugLogging
from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_INTO_FLOOR
from src.physics import COLLIDE_MASK_INTO_PLAYER
from src.physics import COLLIDE_MASK_INTO_WALL
from src.physics import initPhysics
from src.physics import onCollideEventIn
from src.physics import onCollideEventOut
from src.world_config import PLAYER_HEIGHT

log = newLogger(__name__)

LOG_DEBUG = False

def main():
    log.info("Begin.")

    if LOG_DEBUG:
        enableDebugLogging()
        log.info("Debug logging enabled.")
        log.debug("Debug logging enabled.")
    else:
        log.info("Debug logging disabled.")

    app = MyApp()

    # Sigh. Other modules can't just import app from us, because Python imports
    # are dumb. If you write:
    #     from x import y
    # then it binds the local name y to _the current value_ of x.y. But if x
    # later overwrites y, then your module's variable y still refers to the old
    # value of x.y! See:
    #     https://docs.python.org/2.7/reference/
    #         simple_stmts.html#the-import-statement
    # In short, AFAIK Python doesn't have any mechanism to actually share a
    # global between two modules. The best you can do is to setup two separate
    # variables that point to the same thing, and then make sure you never
    # change them thereafter.
    #
    # A workaround is to use the regular 'import x' and then refer to the
    # variable as x.y everywhere, but that has 2 disadvantages:
    #   1. It's more verbose
    #   2. It loses some static checking -- if x has no y, then this method
    #      will only fail when you actually execute some code that refers to
    #      x.y; the other method would fail at startup because it couldn't
    #      import the name.
    # There are more exotic workarounds, but a lot of them aren't very good:
    #   - Create a global object in x whose sole purpose is to store variables;
    #     use x.varHolder.y everywhere.
    #   - Make all your globals arrays of length 1, so that they're references
    #     and you can copy the references.
    #
    # Currently we have only one global that needs to be shared (app), and it
    # only needs to be overwritten once (in main()). So we can get away with
    # the following solution: in each module, have an init function which takes
    # in app and stores it as a global in that module; in main(), call all
    # those init()s after we've finished initializing app. I am sure that some
    # would argue that this is "better design", but I am skeptical that it will
    # scale well. For now, though, it works.
    initModules(app)

    app.initCollisionHandling()
    app.initObjects()
    app.initPlayer()
    app.initKeyboardAndMouse()

    app.run()

    # Not reached; I think Panda3D calls sys.exit when you close the window.
    log.info("End.")

def initModules(app):
    initControl(app)
    initGraphics(app)
    initPhysics(app)

class MyApp(ShowBase):

    ###########################################################################
    # Initialization

    def __init__(self):
        ShowBase.__init__(self)

        # MOVE-TO: ???
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

        # MOVE-TO/TODO[#2]: Maybe have the canonical def. in physics, but also
        # a reference as app.cTrav?
        # TODO[#2]: cTrav exists before we initialize it here; it just has the
        # value 0. Can we just overwrite it in initPhysics and not initialize
        # it here at all?
        self.cTrav = CollisionTraverser()

    def initCollisionHandling(self):
        """
        Initialize the collision handlers. This must be run before any objects
        are created.
        """

        # TODO[#2]: Have physics.py expose a function to add colliders
        # Used to handle collisions between physics-affected objects.
        physics.physicsCollisionHandler = PhysicsCollisionHandler()

        # Used to run custom code on collisions.
        physics.eventCollisionHandler = CollisionHandlerEvent()

        physics.eventCollisionHandler.addInPattern("%fn-into-%in")
        physics.eventCollisionHandler.addOutPattern("%fn-out-%in")

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

        # TODO: Magic numbers bad (position and scale)
        scene = self.loader.loadModel("models/environment")
        scene.reparentTo(self.render)
        scene.setScale(0.25, 0.25, 0.25)
        scene.setPos(-8, 42, 0)

        # Add collision geometry for the ground. For now, it's just an infinite
        # plane; eventually we should figure out how to actually match it with
        # the environment model.
        groundCollider = self.render.attachNewNode(
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
        graphics.smileyNP = self.render.attachNewNode("SmileyNP")
        # Lift the smiley/frowney up a bit so that if the player runs into it,
        # it'll try to push them down. This used to demonstrate a bug where the
        # ground didn't push back and so the player would just be pushed
        # underground. At this point it's just for historical reasons.
        graphics.smileyNP.setPos(-5, 10, 1.25)

        graphics.smileyModel = self.loader.loadModel("smiley")
        graphics.smileyModel.reparentTo(graphics.smileyNP)
        graphics.frowneyModel = self.loader.loadModel("frowney")

        smileyCollide = graphics.smileyNP.attachNewNode(
            CollisionNode("SmileyCollide")
        )
        # The smiley is logically a wall, so set its into collision mask as
        # such.
        smileyCollide.node().setIntoCollideMask(COLLIDE_MASK_INTO_WALL)
        smileyCollide.node().addSolid(CollisionSphere(0, 0, 0, 1))

    def initPlayer(self):
        # TODO[#2]: Functions in graphics.py to set pos and hpr.
        # TODO[#2]: ...what about the physics code in control.py?
        # playerNP is at the player's feet, not their center of mass.
        graphics.playerNP = self.render.attachNewNode(ActorNode("Player"))
        graphics.playerNP.setPos(0, 0, 0)
        self.physicsMgr.attachPhysicalNode(graphics.playerNP.node())
        graphics.playerHeadNP = graphics.playerNP.attachNewNode("PlayerHead")
        # Put the player's head a little below the actual top of the player so
        # that if you're standing right under an object, the object is still
        # within your camera's viewing frustum.
        graphics.playerHeadNP.setPos(0, 0, PLAYER_HEIGHT - 0.2)
        self.camera.reparentTo(graphics.playerHeadNP)
        # Move the camera's near plane closer than the default (1) so that when
        # the player butts their head against a wall, they don't see through
        # it. In general, this distance should be close enough that the near
        # plane stays within the player's hitbox (even as the player's head
        # rotates in place). For more on camera/lens geometry in Panda3D, see:
        #     https://www.panda3d.org/manual/index.php/Lenses_and_Field_of_View
        self.camLens.setNear(0.1)

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
        self.cTrav.addCollider(playerCollider,
                               physics.physicsCollisionHandler)

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

