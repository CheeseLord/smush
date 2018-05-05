import math
import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import BitMask32
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
from src.logconfig import enableDebugLogging
from src.logconfig import newLogger
from src.utils import constrainToInterval, moveVectorTowardByAtMost

log = newLogger(__name__)

LOG_DEBUG = False

# MOVE-TO: control.py
FRAMES_NEEDED_TO_WARP = 2

# MOVE-TO: world_config.py
PLAYER_HEIGHT = 2.0

# MOVE-TO: world_config.py (or possibly physics.py?)
# Magnitude.
GRAVITY_ACCEL = 9.81

# MOVE-TO: physics.py
# Bitmasks for the "into" colliders
# TODO: Remove "INTO_" from these names? It makes them kind of needlessly long,
# especially since we don't have any COLLIDE_MASK_FROMs...
COLLIDE_MASK_INTO_NONE   = BitMask32(0x0)
COLLIDE_MASK_INTO_FLOOR  = BitMask32(0x1)
COLLIDE_MASK_INTO_WALL   = BitMask32(0x2)
COLLIDE_MASK_INTO_PLAYER = BitMask32(0x4)
COLLIDE_MASK_INTO_ENTITY = BitMask32(0x8) # For misc entities flying around

# MOVE-TO: main.py (from here to the bottom of class MyApp)
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


###########################################################################
# Other (unsorted)

# MOVE-TO: physics.py
def onCollideEventIn(entry):
    log.debug("Collision detected IN.")
    # There, pylint, I used the parameter. Happy?
    log.debug("    %s", entry)

    # Get rid of the bullet.
    bullet = entry.getFromNode().getParent(0)
    bullet.getParent(0).removeChild(bullet)

    toggleSmileyFrowney()

def onCollideEventOut(entry):
    # Note: I'm not sure we actually care about handling the "out" events.
    log.debug("Collision detected OUT.")
    log.debug("    %s", entry)

# MOVE-TO: graphics.py
def toggleSmileyFrowney():
    if not app.smileyIsFrowney:
        app.smileyModel.detachNode()
        app.frowneyModel.reparentTo(app.smileyNP)
    else:
        app.frowneyModel.detachNode()
        app.smileyModel.reparentTo(app.smileyNP)
    app.smileyIsFrowney = not app.smileyIsFrowney

# MOVE-TO: control.py
# We don't use task, but we can't remove it because the function signature
# is from Panda3D.
def movePlayerTask(task):  # pylint: disable=unused-argument
    dt = app.globalClock.getDt()

    # TODO: Blah blah magic numbers bad. But actually though, can we put
    # all these in a config file?

    # TODO: Have different maximum forward/sideways/backward velocity
    # components. Something like this:
    #
    # forwardSpeed  = 20
    # sidewaysSpeed = 15
    # backwardSpeed = 10

    # In meters per second.
    # TODO: This is too high... if we rescale the environment more sanely
    # can it feel natural with a not-absurd top speed?
    maxSpeed = 15

    timeToReachTopSpeed = 0.3
    maxAccel = maxSpeed / timeToReachTopSpeed

    # Degrees per second.
    rotateSpeed   = 90

    # See:
    #     https://www.panda3d.org/manual/index.php/Keyboard_Support
    # section "Polling interface"
    moveFwd   = app.mouseWatcherNode.is_button_down("w")
    moveLeft  = app.mouseWatcherNode.is_button_down("a")
    moveRight = app.mouseWatcherNode.is_button_down("d")
    moveBack  = app.mouseWatcherNode.is_button_down("s")
    turnLeft  = app.mouseWatcherNode.is_button_down("q")
    turnRight = app.mouseWatcherNode.is_button_down("e")
    jump      = app.mouseWatcherNode.is_button_down("space")

    # TODO: Handle rotations by setting angular velocity instead of
    # instantaneously changing HPR.
    # x is sideways and y is forward. A positive rotation is to the left.
    rotateAmt = (turnLeft - turnRight) * rotateSpeed * dt
    app.playerNP.setHpr(app.playerNP, rotateAmt, 0, 0)

    # Compute direction of target velocity in x,y-plane.
    netRunRight = moveRight - moveLeft
    netRunFwd   = moveFwd   - moveBack
    # TODO: Does this go before or after we add in the z?
    targetVel = app.render.getRelativeVector(
        app.playerNP,
        Vec3(netRunRight, netRunFwd, 0)
    )

    # Rescale to desired magnitude (if not zero).
    if netRunFwd != 0 or netRunRight != 0:
        targetVel *= maxSpeed / targetVel.length()

    # Copy z from current velocity.
    playerPhysicsObj = app.playerNP.node().getPhysicsObject()
    currPlayerVel = playerPhysicsObj.getVelocity()
    playerZVel = currPlayerVel.getZ()
    targetVel += Vec3(0, 0, playerZVel)

    # Move current velocity toward target velocity by at most a*dt
    newPlayerVel = moveVectorTowardByAtMost(currPlayerVel, targetVel,
                                            maxAccel * dt)

    # Allow the player to jump, but only if they're standing on the ground.
    # TODO: Really this should be "but only if there's ground beneath their
    # feet, regardless of z coordinate", but I don't know how to check for
    # that.
    # Also only allow jumping if they're not already going up. I don't know
    # how this can happen, but it has been observed.
    if jump and -0.001 <= app.playerNP.getZ() <= 0.001 and \
            playerZVel <= 0.001:
        jumpHeight = 1.1
        jumpSpeed = math.sqrt(2 * GRAVITY_ACCEL * jumpHeight)
        newPlayerVel += Vec3(0, 0, jumpSpeed)

    playerPhysicsObj.setVelocity(newPlayerVel)

    return Task.cont

# MOVE-TO: control.py
def controlCameraTask(task):  # pylint: disable=unused-argument
    # Degrees per pixel
    mouseGain = 0.25

    mouseData = app.win.getPointer(0)
    mouseX = mouseData.getX()
    mouseY = mouseData.getY()

    centerX = app.win.getXSize() / 2
    centerY = app.win.getYSize() / 2

    # If our window doesn't have the focus, then this call will fail. In
    # that case, don't move the camera based on the mouse because we're
    # just going to re-apply the same mouse motion on the next frame, so
    # that would cause the camera to go spinning wildly out of control.
    mouseWarpSucceeded = app.win.movePointer(0, centerX, centerY)

    # Also don't move the camera if, since the last failed attempt to warp
    # the mouse, we have not had at least FRAMES_NEEDED_TO_WARP successful
    # warps. In that case, we have not yet finished resolving the first
    # mouse warp since the mouse last entered the window, which means that
    # the mouse's current position can't be trusted to be a meaningful
    # relative value.
    if mouseWarpSucceeded and \
            app.successfulMouseWarps >= FRAMES_NEEDED_TO_WARP:
        # I don't know why these negative signs work but they stop the
        # people being upside-down.
        deltaHeading = (mouseX - centerX) * -mouseGain
        deltaPitch   = (mouseY - centerY) * -mouseGain

        # Note that the heading change is applied to the playerNP, while
        # the pitch is applied to the playerHeadNP. You can use the mouse
        # to turn from side to side, which affects your movement, but there
        # is no way to tilt the player upward or downward because you're
        # always standing upright.

        # For heading, just adjust by the appropriate amount.
        app.playerNP.setHpr(app.playerNP, deltaHeading, 0, 0)

        # For pitch, we need to be more careful. If we just call setHpr to
        # adjust the pitch, then Panda3D will apply the full rotation,
        # which means you can wind up facing backwards. But if we then call
        # getP() to get the pitch, it will still return a value between -90
        # and 90, which means we can't fix it up after the fact. Instead,
        # add the delta to the pitch outside of Panda3D, so that we can
        # detect and fix the case where the player has tried to look too
        # high or low (by capping them to just under 90 degrees in either
        # direction).
        newPitch = app.playerHeadNP.getP() + deltaPitch
        newPitch = constrainToInterval(newPitch, -89, 89)
        app.playerHeadNP.setP(newPitch)

    if mouseWarpSucceeded:
        # Prevent this value from growing out of control, on principle.
        if app.successfulMouseWarps < FRAMES_NEEDED_TO_WARP:
            app.successfulMouseWarps += 1
    else:
        app.successfulMouseWarps = 0

    return Task.cont

# MOVE-TO: control.py
# TODO: Probably split this up, have a separate call for "shoot gun".
def clicked():
    # NOTE: This kind of actor has nothing to do with the graphics kind.
    physicsNP = app.render.attachNewNode(ActorNode("smileyPhysics"))
    app.physicsMgr.attachPhysicalNode(physicsNP.node())

    playerVel = app.playerNP.node().getPhysicsObject().getVelocity()
    bulletVel = app.render.getRelativeVector(app.playerHeadNP,
                                             Vec3(0, 30, 0))

    # TODO: Also account for the player's angular velocity.
    physicsNP.node().getPhysicsObject().setVelocity(playerVel + bulletVel)

    ball = app.loader.loadModel("smiley")
    ball.reparentTo(physicsNP)
    ball.setScale(0.02)
    physicsNP.setHpr(app.playerNP.getHpr())
    physicsNP.setPos(app.render.getRelativePoint(app.playerHeadNP,
                                                 Point3(0, 0, 0)))

    # Also add collision geometry to the bullet
    bulletColliderPhys = physicsNP.attachNewNode(
        CollisionNode("BulletColliderPhys")
    )
    bulletColliderPhys.node().setIntoCollideMask(COLLIDE_MASK_INTO_ENTITY)
    bulletColliderPhys.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
                                                 COLLIDE_MASK_INTO_WALL  |
                                                 COLLIDE_MASK_INTO_ENTITY)
    bulletColliderPhys.node().addSolid(CollisionSphere(0, 0, 0, 0.02))

    # We can't have two collision handlers for the same collision node. But
    # we can create two collision nodes with the same geometry, reparent
    # one to the other so they always have the same position, and then have
    # one collision handler for each.
    bulletColliderEvt = physicsNP.attachNewNode(
        CollisionNode("BulletColliderEvt")
    )
    # Don't allow anything to collide into the bulletColliderEvt. I am
    # doing this to fix a problem where bullets would go flying off in
    # weird directions when we changed bulletColliderEvt to be a child of
    # physicsNP instead of a child of bulletColliderPhys. I _think_ the
    # problem was that the bulletColliderPhys was colliding into the
    # bulletColliderEvt. It seems reasonable to me to disallow all
    # collisions into the bulletColliderEvt, since anything that needs to
    # collide into the bullet can already collide into the
    # bulletColliderPhys.
    #
    # Note that the bulletColliderEvt is probably still colliding into the
    # bulletColliderPhys, but since we have no handler for that collision
    # it's harmless.
    bulletColliderEvt.node().setIntoCollideMask(COLLIDE_MASK_INTO_NONE)
    bulletColliderEvt.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
                                                COLLIDE_MASK_INTO_WALL  |
                                                COLLIDE_MASK_INTO_ENTITY)
    bulletColliderEvt.node().addSolid(CollisionSphere(0, 0, 0, 0.02))

    # Handle collisions through physics via bulletColliderPhys.
    app.physicsCollisionHandler.addCollider(bulletColliderPhys, physicsNP)
    app.cTrav.addCollider(bulletColliderPhys, app.physicsCollisionHandler)

    # Handle collisions in custom manner via bulletColliderEvt.
    app.cTrav.addCollider(bulletColliderEvt, app.eventCollisionHandler)


if __name__ == "__main__":
    main()

