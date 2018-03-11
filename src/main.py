import math
import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import BitMask32
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
from src.utils import constrainToInterval

log = newLogger(__name__)

LOG_DEBUG = False

FRAMES_NEEDED_TO_WARP = 2
PLAYER_HEIGHT = 2.0

# Magnitude.
GRAVITY_ACCEL = 9.81

# Bitmasks for the "into" colliders
# TODO: Remove "INTO_" from these names? It makes them kind of needlessly long,
# especially since we don't have any COLLIDE_MASK_FROMs...
COLLIDE_MASK_INTO_NONE   = BitMask32(0x0)
COLLIDE_MASK_INTO_FLOOR  = BitMask32(0x1)
COLLIDE_MASK_INTO_WALL   = BitMask32(0x2)
COLLIDE_MASK_INTO_PLAYER = BitMask32(0x4)
COLLIDE_MASK_INTO_ENTITY = BitMask32(0x8) # For misc entities flying around

def main():
    log.info("Begin.")

    if LOG_DEBUG:
        enableDebugLogging()

    app = MyApp()
    app.run()

    # Not reached; I think Panda3D calls sys.exit when you close the window.
    log.info("End.")

class MyApp(ShowBase):
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

        # Add collision handler
        self.cTrav = CollisionTraverser()

        # Start the physics (yes, with the particle engine).
        self.enableParticles()
        gravityNode = ForceNode("world-forces")
        gravityForce = LinearVectorForce(0, 0, -GRAVITY_ACCEL)
        gravityNode.addForce(gravityForce)
        self.physicsMgr.addLinearForce(gravityForce)

        # Load the environment model.
        self.scene = self.loader.loadModel("models/environment")
        self.scene.reparentTo(self.render)

        # Apply scale and position transforms on the model.
        # Something something magic numbers bad something something.
        self.scene.setScale(0.25, 0.25, 0.25)
        self.scene.setPos(-8, 42, 0)

        # Bring in a smily model, with a collision geometry. More or less
        # stolen from one of the examples on this page:
        #     https://www.panda3d.org/forums/viewtopic.php?t=7918
        self.smiley = self.loader.loadModel("smiley")
        self.smileyCollide = self.smiley.attachNewNode(
            CollisionNode("SmileyCollide")
        )
        # The smiley is logically a wall, so set its into collision mask as
        # such.
        self.smileyCollide.node().setIntoCollideMask(COLLIDE_MASK_INTO_WALL)
        # TODO: Why .node()? Can't add a solid to a NodePath?
        self.smileyCollide.node().addSolid(CollisionSphere(0, 0, 0, 1))
        self.smiley.reparentTo(self.render)
        # Lift the smiley up some so the player will more consistently be
        # pushed underground.
        self.smiley.setPos(-5, 10, 1.25)

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

        # Used to handle collisions between physics-affected objects.
        self.physicsCollisionHandler = PhysicsCollisionHandler()

        # For colliding the player with walls and other such obstacles to
        # horizontal motion.
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

        # Add collision geometry for the ground. For now, it's just an infinite
        # plane; eventually we should figure out how to actually match it with
        # the environment model.
        self.groundCollider = self.render.attachNewNode(
            CollisionNode("groundCollider")
        )
        self.groundCollider.node().setIntoCollideMask(
            COLLIDE_MASK_INTO_FLOOR
        )
        self.groundCollider.node().addSolid(
            CollisionPlane(Plane(Vec3(0, 0, 1), Point3(0, 0, 0)))
        )

        # Hide the mouse.
        self.disableMouse()
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)
        self.taskMgr.add(self.controlCamera, "camera-task")

        # How many previous frames have we successfully warped the mouse? Only
        # tracked up to FRAMES_NEEDED_TO_WARP.
        self.successfulMouseWarps = 0

        self.setupEventHandlers()
        self.taskMgr.add(self.movePlayerTask, "MovePlayerTask")

    def setupEventHandlers(self):
        # Provide a way to exit even when we make the window fullscreen.
        self.accept('control-q', sys.exit)

        # Handle the mouse.
        self.accept("mouse1", self.clicked, [])

        # Camera toggle.
        # self.accept("f3",       self.toggleCameraStyle, [])

        # Handle window close request (clicking the X, Alt-F4, etc.)
        # self.win.set_close_request_event("window-close")
        # self.accept("window-close", self.handleWindowClose)

    # We don't use task, but we can't remove it because the function signature
    # is from Panda3D.
    def movePlayerTask(self, task):  # pylint: disable=unused-argument
        dt = self.globalClock.getDt()

        # TODO: Blah blah magic numbers bad. But actually though, can we put
        # all these in a config file?

        # In arbitrary units of length per second.
        forwardSpeed  = 20
        sidewaysSpeed = 15
        backwardSpeed = 10

        # Degrees per second.
        rotateSpeed   = 90

        # See:
        #     https://www.panda3d.org/manual/index.php/Keyboard_Support
        # section "Polling interface"
        moveFwd   = self.mouseWatcherNode.is_button_down("w")
        moveLeft  = self.mouseWatcherNode.is_button_down("a")
        moveRight = self.mouseWatcherNode.is_button_down("d")
        moveBack  = self.mouseWatcherNode.is_button_down("s")
        turnLeft  = self.mouseWatcherNode.is_button_down("q")
        turnRight = self.mouseWatcherNode.is_button_down("e")
        jump      = self.mouseWatcherNode.is_button_down("space")

        # TODO: Handle rotations by setting angular velocity instead of
        # instantaneously changing HPR.
        # x is sideways and y is forward. A positive rotation is to the left.
        rotateAmt = (turnLeft - turnRight) * rotateSpeed * dt
        self.playerNP.setHpr(self.playerNP, rotateAmt, 0, 0)

        rightVel = (moveRight - moveLeft) * sidewaysSpeed
        fwdVel   = 0
        if moveFwd and not moveBack:
            fwdVel = forwardSpeed
        elif moveBack and not moveFwd:
            fwdVel = -backwardSpeed

        playerVel = self.render.getRelativeVector(self.playerNP,
                                                  Vec3(rightVel, fwdVel, 0))

        # Preserve the z component of the player's old velocity.
        playerPhysicsObj = self.playerNP.node().getPhysicsObject()
        playerZVel = playerPhysicsObj.getVelocity().getZ()
        playerVel += Vec3(0, 0, playerZVel)

        # Allow the player to jump, but only if they're standing on the ground.
        # TODO: Really this should be "but only if there's ground beneath their
        # feet, regardless of z coordinate", but I don't know how to check for
        # that.
        # Also only allow jumping if they're not already going up. I don't know
        # how this can happen, but it has been observed.
        if jump and -0.001 <= self.playerNP.getZ() <= 0.001 and \
                playerZVel <= 0.001:
            jumpHeight = 1.1
            jumpSpeed = math.sqrt(2 * GRAVITY_ACCEL * jumpHeight)
            playerVel += Vec3(0, 0, jumpSpeed)

        playerPhysicsObj.setVelocity(playerVel)

        return Task.cont

    def controlCamera(self, task):  # pylint: disable=unused-argument
        # Degrees per pixel
        mouseGain = 0.25

        mouseData = self.win.getPointer(0)
        mouseX = mouseData.getX()
        mouseY = mouseData.getY()

        centerX = self.win.getXSize() / 2
        centerY = self.win.getYSize() / 2

        # If our window doesn't have the focus, then this call will fail. In
        # that case, don't move the camera based on the mouse because we're
        # just going to re-apply the same mouse motion on the next frame, so
        # that would cause the camera to go spinning wildly out of control.
        mouseWarpSucceeded = self.win.movePointer(0, centerX, centerY)

        # Also don't move the camera if, since the last failed attempt to warp
        # the mouse, we have not had at least FRAMES_NEEDED_TO_WARP successful
        # warps. In that case, we have not yet finished resolving the first
        # mouse warp since the mouse last entered the window, which means that
        # the mouse's current position can't be trusted to be a meaningful
        # relative value.
        if mouseWarpSucceeded and \
                self.successfulMouseWarps >= FRAMES_NEEDED_TO_WARP:
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
            self.playerNP.setHpr(self.playerNP, deltaHeading, 0, 0)

            # For pitch, we need to be more careful. If we just call setHpr to
            # adjust the pitch, then Panda3D will apply the full rotation,
            # which means you can wind up facing backwards. But if we then call
            # getP() to get the pitch, it will still return a value between -90
            # and 90, which means we can't fix it up after the fact. Instead,
            # add the delta to the pitch outside of Panda3D, so that we can
            # detect and fix the case where the player has tried to look too
            # high or low (by capping them to just under 90 degrees in either
            # direction).
            newPitch = self.playerHeadNP.getP() + deltaPitch
            newPitch = constrainToInterval(newPitch, -89, 89)
            self.playerHeadNP.setP(newPitch)

        if mouseWarpSucceeded:
            # Prevent this value from growing out of control, on principle.
            if self.successfulMouseWarps < FRAMES_NEEDED_TO_WARP:
                self.successfulMouseWarps += 1
        else:
            self.successfulMouseWarps = 0

        return Task.cont

    def clicked(self):
        # NOTE: This kind of actor has nothing to do with the graphics kind.
        physicsNP = self.render.attachNewNode(ActorNode("smileyPhysics"))
        self.physicsMgr.attachPhysicalNode(physicsNP.node())

        playerVel = self.playerNP.node().getPhysicsObject().getVelocity()
        bulletVel = self.render.getRelativeVector(self.playerHeadNP,
                                                  Vec3(0, 30, 0))

        # TODO: Also account for the player's angular velocity.
        physicsNP.node().getPhysicsObject().setVelocity(playerVel + bulletVel)

        ball = self.loader.loadModel("smiley")
        ball.reparentTo(physicsNP)
        ball.setScale(0.02)
        physicsNP.setHpr(self.playerNP.getHpr())
        physicsNP.setPos(self.render.getRelativePoint(self.playerHeadNP,
                                                      Point3(0, 0, 0)))

        # Also add collision geometry to the bullet
        bulletCollider = physicsNP.attachNewNode(
            CollisionNode("BulletCollider")
        )
        bulletCollider.node().setIntoCollideMask(COLLIDE_MASK_INTO_ENTITY)
        bulletCollider.node().setFromCollideMask(COLLIDE_MASK_INTO_FLOOR |
                                                 COLLIDE_MASK_INTO_WALL  |
                                                 COLLIDE_MASK_INTO_ENTITY)
        bulletCollider.node().addSolid(CollisionSphere(0, 0, 0, 0.02))

        # And handle its collisions with the ground.
        self.physicsCollisionHandler.addCollider(bulletCollider, physicsNP)
        self.cTrav.addCollider(bulletCollider, self.physicsCollisionHandler)


if __name__ == "__main__":
    main()

