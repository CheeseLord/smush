import math
import sys

from direct.showbase.InputStateGlobal import inputState
from direct.task import Task

from panda3d.bullet import BulletRigidBodyNode
from panda3d.bullet import BulletSphereShape
from panda3d.core import Point3
from panda3d.core import Vec3
from panda3d.core import WindowProperties

from src.graphics import changePlayerHeadingPitch
from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_BULLET
from src.world import makePlayerBullet
from src.world_config import GRAVITY_ACCEL

# FIXME[bullet]
from src import graphics

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

    # Handle window close request (clicking the X, Alt-F4, etc.)
    # app.win.set_close_request_event("window-close")
    # app.accept("window-close", handleWindowClose)

    # Setup watchers for the control keys
    inputState.watchWithModifiers("moveFwd",   "w")
    inputState.watchWithModifiers("moveBack",  "s")
    inputState.watchWithModifiers("moveLeft",  "a")
    inputState.watchWithModifiers("moveRight", "d")
    inputState.watchWithModifiers("turnLeft",  "q")
    inputState.watchWithModifiers("turnRight", "e")
    inputState.watchWithModifiers("jump",      "space")

    app.taskMgr.add(controlCameraTask, "ControlCameraTask")
    app.taskMgr.add(movePlayerTask,    "MovePlayerTask")


# We don't use task, but we can't remove it because the function signature
# is from Panda3D.
# TODO: Rename this. This is the function that moves the player based on the
# keyboard.
def movePlayerTask(task):  # pylint: disable=unused-argument
    # TODO: Blah blah magic numbers bad. But actually though, can we put
    # all these in a config file?

    # TODO: Have different maximum forward/sideways/backward velocity
    # components. Something like this:
    #
    # forwardSpeed  = 20
    # sidewaysSpeed = 15
    # backwardSpeed = 10

    # In meters per second.
    # FIXME: The player does not move at 15 m/s. What units does this use??
    # TODO: This is too high... if we rescale the environment more sanely
    # can it feel natural with a not-absurd top speed?
    maxSpeed = 15

    # TODO[bullet]: Make the player accelerate to a top speed, rather than
    # instantaneously changing their velocity. Some parameters from before:
    #
    # timeToReachTopSpeed = 0.3
    # maxAccel = maxSpeed / timeToReachTopSpeed

    # Degrees per second.
    maxRotateSpeed = 90

    netRunRight = 0
    netRunFwd   = 0
    rotateSpeed = 0

    # Compute direction of target velocity in x,y-plane.
    # TODO[bullet]: If moving diagonally, scale down. Really we want to just
    # compute the direction here, and then scale (if nonzero) down to magnitude
    # maxSpeed.
    if inputState.isSet("moveFwd"):
        netRunFwd   += maxSpeed
    if inputState.isSet("moveBack"):
        netRunFwd   -= maxSpeed
    if inputState.isSet("moveLeft"):
        netRunRight -= maxSpeed
    if inputState.isSet("moveRight"):
        netRunRight += maxSpeed

    # x is sideways and y is forward. A positive rotation is to the left.
    # TODO: Handle rotations by setting angular velocity instead of
    # instantaneously changing HPR.
    if inputState.isSet("turnLeft"):
        rotateSpeed += maxRotateSpeed
    if inputState.isSet("turnRight"):
        rotateSpeed -= maxRotateSpeed

    # FIXME[bullet]: What about old z velocity from a previous jump??
    playerVel = Vec3(netRunRight, netRunFwd, 0)
    graphics.playerNP.node().setLinearMovement (playerVel, True)
    graphics.playerNP.node().setAngularMovement(rotateSpeed)

    if inputState.isSet("jump"):
        jumpHeight = 1.1
        jumpSpeed = math.sqrt(2 * GRAVITY_ACCEL * jumpHeight)
        # Note: some example code makes this call as well, but I don't think it
        # has any effect...
        # graphics.playerNP.node().setMaxJumpHeight(jumpHeight)
        graphics.playerNP.node().setJumpSpeed(jumpSpeed)
        graphics.playerNP.node().doJump()

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

    centerX = app.win.getXSize() // 2
    centerY = app.win.getYSize() // 2

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
    if mouseWarpSucceeded and successfulMouseWarps >= FRAMES_NEEDED_TO_WARP:
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


def clicked():
    makePlayerBullet()

