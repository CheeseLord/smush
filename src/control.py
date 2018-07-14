import math
import sys

from direct.task import Task

from panda3d.bullet import BulletSphereShape
from panda3d.bullet import BulletRigidBodyNode
from panda3d.core import ClockObject
# from panda3d.core import CollisionNode
# from panda3d.core import CollisionSphere
from panda3d.core import Vec3
from panda3d.core import WindowProperties
# from panda3d.physics import ActorNode

from src.graphics import changePlayerHeadingPitch
from src.graphics import getPlayerHeadingPitch
from src.graphics import getPlayerHeadPos
from src.graphics import getPlayerPos
from src.graphics import getRelativePlayerHeadVector
from src.graphics import getRelativePlayerVector
from src.logconfig import newLogger
# from src.physics import COLLIDE_MASK_INTO_ENTITY
# from src.physics import COLLIDE_MASK_INTO_FLOOR
# from src.physics import COLLIDE_MASK_INTO_NONE
# from src.physics import COLLIDE_MASK_INTO_WALL
# from src.physics import addBulletColliders
from src.physics import getPlayerVel
from src.physics import setPlayerVel
from src.utils import moveVectorTowardByAtMost
from src.world_config import GRAVITY_ACCEL

# FIXME[bullet]
from src import physics

log = newLogger(__name__)

FRAMES_NEEDED_TO_WARP = 2

app = None

# How many previous frames have we successfully warped the mouse? Only tracked
# up to FRAMES_NEEDED_TO_WARP.
successfulMouseWarps = 0

def initControl(app_):
    # Why does 'global x' cause pylint to assume x is a constant? If I wanted
    # to use x as a constant I'd just reference it; I wouldn't go to the
    # trouble of adding a declaration that allows me to write to it.
    global app
    app = app_

    initKeyboardAndMouse()

def initKeyboardAndMouse():
    # Hide the mouse.
    app.disableMouse()
    props = WindowProperties()
    props.setCursorHidden(True)
    app.win.requestProperties(props)

    # Provide a way to exit even when we make the window fullscreen.
    app.accept('control-q', sys.exit)

    # Handle the mouse.
    app.accept("mouse1", clicked, [])

    # Camera toggle.
    # app.accept("f3", toggleCameraStyle, [])

    # Handle window close request (clicking the X, Alt-F4, etc.)
    # app.win.set_close_request_event("window-close")
    # app.accept("window-close", handleWindowClose)

    app.taskMgr.add(controlCameraTask, "ControlCameraTask")
    app.taskMgr.add(movePlayerTask,    "MovePlayerTask")

# We don't use task, but we can't remove it because the function signature
# is from Panda3D.
# TODO: Rename this. This is the function that moves the player based on the
# keyboard.
def movePlayerTask(task):  # pylint: disable=unused-argument
    dt = ClockObject.getGlobalClock().getDt()

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
    changePlayerHeadingPitch(rotateAmt, 0)

    # Compute direction of target velocity in x,y-plane.
    netRunRight = moveRight - moveLeft
    netRunFwd   = moveFwd   - moveBack
    # TODO: Does this go before or after we add in the z?
    targetVel = getRelativePlayerVector(Vec3(netRunRight, netRunFwd, 0))

    # Rescale to desired magnitude (if not zero).
    if netRunFwd != 0 or netRunRight != 0:
        targetVel *= maxSpeed / targetVel.length()

    # Copy z from current velocity.
    currPlayerVel = getPlayerVel()
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
    _, _, playerZ = getPlayerPos()
    if jump and -0.001 <= playerZ <= 0.001 and playerZVel <= 0.001:
        jumpHeight = 1.1
        jumpSpeed = math.sqrt(2 * GRAVITY_ACCEL * jumpHeight)
        newPlayerVel += Vec3(0, 0, jumpSpeed)

    setPlayerVel(newPlayerVel)

    return Task.cont

# TODO: Rename this. This is the function that moves the player based on the
# mouse.
def controlCameraTask(task):  # pylint: disable=unused-argument
    global successfulMouseWarps

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
            successfulMouseWarps >= FRAMES_NEEDED_TO_WARP:
        # I don't know why these negative signs work but they stop the
        # people being upside-down.
        deltaHeading = (mouseX - centerX) * -mouseGain
        deltaPitch   = (mouseY - centerY) * -mouseGain
        changePlayerHeadingPitch(deltaHeading, deltaPitch)

    if mouseWarpSucceeded:
        # Prevent this value from growing out of control, on principle.
        if successfulMouseWarps < FRAMES_NEEDED_TO_WARP:
            successfulMouseWarps += 1
    else:
        successfulMouseWarps = 0

    return Task.cont

# TODO: Probably split this up, have a separate call for "shoot gun".
def clicked():
    radius = 0.02
    shape = BulletSphereShape(radius)

    node = BulletRigidBodyNode("smiling bullet")
    node.setMass(0.05)
    node.addShape(shape)

    # https://www.panda3d.org/manual/index.php/
    #     Bullet_Continuous_Collision_Detection
    node.setCcdMotionThreshold(1e-7)
    node.setCcdSweptSphereRadius(radius)

    physicsNP = app.render.attachNewNode(node)
    physics.world.attachRigidBody(node)

    # NOTE: This kind of actor has nothing to do with the graphics kind.
    # physicsNP = app.render.attachNewNode(ActorNode("smileyPhysics"))
    # app.physicsMgr.attachPhysicalNode(physicsNP.node())

    # Note: see
    #     https://www.panda3d.org/manual/index.php/
    #         Bullet_Continuous_Collision_Detection
    # for an alternate strategy for aiming a bullet where the player is
    # looking. The example code there uses base.camLens.extrude.
    playerVel = getPlayerVel()
    bulletVel = getRelativePlayerHeadVector(Vec3(0, 30, 0))

    # TODO: Also account for the player's angular velocity.
    # physicsNP.node().getPhysicsObject().setVelocity(playerVel + bulletVel)
    node.setLinearVelocity(playerVel + bulletVel)

    ball = app.loader.loadModel("smiley")
    ball.reparentTo(physicsNP)
    ball.setScale(radius)
    # Intentionally don't set the pitch, because the balls can't roll and it
    # would look weird if they were all stuck at different arbitrary pitches.
    # TODO[bullet]: They should be able to roll now, so we should set this.
    playerHeading, _ = getPlayerHeadingPitch()
    physicsNP.setH(playerHeading)
    physicsNP.setPos(getPlayerHeadPos())

    # Also add collision geometry to the bullet
    # bulletColliderPhys = physicsNP.attachNewNode(
    #     CollisionNode("BulletColliderPhys")
    # )
    # bulletColliderPhys.node().setIntoCollideMask(COLLIDE_MASK_INTO_ENTITY)
    # bulletColliderPhys.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
    #                                              COLLIDE_MASK_INTO_WALL  |
    #                                              COLLIDE_MASK_INTO_ENTITY)
    # bulletColliderPhys.node().addSolid(CollisionSphere(0, 0, 0, 0.02))

    # # We can't have two collision handlers for the same collision node. But
    # # we can create two collision nodes with the same geometry, reparent
    # # one to the other so they always have the same position, and then have
    # # one collision handler for each.
    # bulletColliderEvt = physicsNP.attachNewNode(
    #     CollisionNode("BulletColliderEvt")
    # )
    # # Don't allow anything to collide into the bulletColliderEvt. I am
    # # doing this to fix a problem where bullets would go flying off in
    # # weird directions when we changed bulletColliderEvt to be a child of
    # # physicsNP instead of a child of bulletColliderPhys. I _think_ the
    # # problem was that the bulletColliderPhys was colliding into the
    # # bulletColliderEvt. It seems reasonable to me to disallow all
    # # collisions into the bulletColliderEvt, since anything that needs to
    # # collide into the bullet can already collide into the
    # # bulletColliderPhys.
    # #
    # # Note that the bulletColliderEvt is probably still colliding into the
    # # bulletColliderPhys, but since we have no handler for that collision
    # # it's harmless.
    # bulletColliderEvt.node().setIntoCollideMask(COLLIDE_MASK_INTO_NONE)
    # bulletColliderEvt.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
    #                                             COLLIDE_MASK_INTO_WALL  |
    #                                             COLLIDE_MASK_INTO_ENTITY)
    # bulletColliderEvt.node().addSolid(CollisionSphere(0, 0, 0, 0.02))

    # addBulletColliders(bulletColliderPhys, bulletColliderEvt, physicsNP)
