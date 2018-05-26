import math

from direct.task import Task
from panda3d.core import CollisionNode
from panda3d.core import CollisionSphere
from panda3d.core import Point3
from panda3d.core import Vec3
from panda3d.physics import ActorNode

from src import graphics # TODO[#2]
from src import physics  # TODO[#2]

from src.logconfig import newLogger
from src.physics import COLLIDE_MASK_INTO_ENTITY
from src.physics import COLLIDE_MASK_INTO_FLOOR
from src.physics import COLLIDE_MASK_INTO_NONE
from src.physics import COLLIDE_MASK_INTO_WALL
from src.utils import constrainToInterval
from src.utils import moveVectorTowardByAtMost
from src.world_config import GRAVITY_ACCEL

log = newLogger(__name__)

FRAMES_NEEDED_TO_WARP = 2

# TODO: figure out something re: pylint and nonconstant globals
app = None # pylint: disable=invalid-name

# How many previous frames have we successfully warped the mouse? Only tracked
# up to FRAMES_NEEDED_TO_WARP.
successfulMouseWarps = 0 # pylint: disable=invalid-name

def initControl(app_):
    # Why does 'global x' cause pylint to assume x is a constant? If I wanted
    # to use x as a constant I'd just reference it; I wouldn't go to the
    # trouble of adding a declaration that allows me to write to it.
    global app # pylint: disable=invalid-name
    app = app_

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
    graphics.playerNP.setHpr(graphics.playerNP, rotateAmt, 0, 0)

    # Compute direction of target velocity in x,y-plane.
    netRunRight = moveRight - moveLeft
    netRunFwd   = moveFwd   - moveBack
    # TODO: Does this go before or after we add in the z?
    targetVel = app.render.getRelativeVector(
        graphics.playerNP,
        Vec3(netRunRight, netRunFwd, 0)
    )

    # Rescale to desired magnitude (if not zero).
    if netRunFwd != 0 or netRunRight != 0:
        targetVel *= maxSpeed / targetVel.length()

    # Copy z from current velocity.
    playerPhysicsObj = graphics.playerNP.node().getPhysicsObject()
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
    if jump and -0.001 <= graphics.playerNP.getZ() <= 0.001 and \
            playerZVel <= 0.001:
        jumpHeight = 1.1
        jumpSpeed = math.sqrt(2 * GRAVITY_ACCEL * jumpHeight)
        newPlayerVel += Vec3(0, 0, jumpSpeed)

    playerPhysicsObj.setVelocity(newPlayerVel)

    return Task.cont

def controlCameraTask(task):  # pylint: disable=unused-argument
    global successfulMouseWarps # pylint: disable=invalid-name

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

        # Note that the heading change is applied to the playerNP, while
        # the pitch is applied to the playerHeadNP. You can use the mouse
        # to turn from side to side, which affects your movement, but there
        # is no way to tilt the player upward or downward because you're
        # always standing upright.

        # For heading, just adjust by the appropriate amount.
        graphics.playerNP.setHpr(graphics.playerNP, deltaHeading, 0, 0)

        # For pitch, we need to be more careful. If we just call setHpr to
        # adjust the pitch, then Panda3D will apply the full rotation,
        # which means you can wind up facing backwards. But if we then call
        # getP() to get the pitch, it will still return a value between -90
        # and 90, which means we can't fix it up after the fact. Instead,
        # add the delta to the pitch outside of Panda3D, so that we can
        # detect and fix the case where the player has tried to look too
        # high or low (by capping them to just under 90 degrees in either
        # direction).
        newPitch = graphics.playerHeadNP.getP() + deltaPitch
        newPitch = constrainToInterval(newPitch, -89, 89)
        graphics.playerHeadNP.setP(newPitch)

    if mouseWarpSucceeded:
        # Prevent this value from growing out of control, on principle.
        if successfulMouseWarps < FRAMES_NEEDED_TO_WARP:
            successfulMouseWarps += 1
    else:
        successfulMouseWarps = 0

    return Task.cont

# TODO: Probably split this up, have a separate call for "shoot gun".
def clicked():
    # NOTE: This kind of actor has nothing to do with the graphics kind.
    physicsNP = app.render.attachNewNode(ActorNode("smileyPhysics"))
    app.physicsMgr.attachPhysicalNode(physicsNP.node())

    playerVel = graphics.playerNP.node().getPhysicsObject().getVelocity()
    bulletVel = app.render.getRelativeVector(graphics.playerHeadNP,
                                             Vec3(0, 30, 0))

    # TODO: Also account for the player's angular velocity.
    physicsNP.node().getPhysicsObject().setVelocity(playerVel + bulletVel)

    ball = app.loader.loadModel("smiley")
    ball.reparentTo(physicsNP)
    ball.setScale(0.02)
    physicsNP.setHpr(graphics.playerNP.getHpr())
    physicsNP.setPos(app.render.getRelativePoint(graphics.playerHeadNP,
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
    physics.physicsCollisionHandler.addCollider(bulletColliderPhys, physicsNP)
    app.cTrav.addCollider(bulletColliderPhys, physics.physicsCollisionHandler)

    # Handle collisions in custom manner via bulletColliderEvt.
    app.cTrav.addCollider(bulletColliderEvt, physics.eventCollisionHandler)

