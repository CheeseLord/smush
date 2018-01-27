import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import WindowProperties, CollisionNode, CollisionSphere

from src.logconfig import newLogger
from src.utils import constrainToInterval

log = newLogger(__name__)

def main():
    log.info("Begin.")

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
        # TODO: Why .node()? Can't add a solid to a NodePath?
        self.smileyCollide.node().addSolid(CollisionSphere(0, 0, 0, 1))
        self.smiley.reparentTo(self.render)
        self.smiley.setPos(-5, 10, 1)

        self.playerNode = self.render.attachNewNode("Player")
        self.playerHeadNode = self.playerNode.attachNewNode("PlayerHead")
        self.playerHeadNode.setPos(0, 0, 1)
        self.camera.reparentTo(self.playerHeadNode)

        # Hide the mouse.
        self.disableMouse()
        props = WindowProperties()
        props.setCursorHidden(True)
        self.win.requestProperties(props)
        self.taskMgr.add(self.controlCamera, "camera-task")

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

        rightDelta = (moveRight - moveLeft) * sidewaysSpeed * dt
        fwdDelta = 0
        if moveFwd and not moveBack:
            fwdDelta = forwardSpeed * dt
        elif moveBack and not moveFwd:
            fwdDelta = -backwardSpeed * dt

        # x is sideways and y is forward. A positive rotation is to the left.
        rotateAmt = (turnLeft - turnRight) * rotateSpeed * dt

        self.playerNode.setPos(self.playerNode, rightDelta, fwdDelta, 0)
        self.playerNode.setHpr(self.playerNode, rotateAmt, 0, 0)

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
        if self.win.movePointer(0, centerX, centerY):
            # I don't know why these negative signs work but they stop the
            # people being upside-down.
            deltaHeading = (mouseX - centerX) * -mouseGain
            deltaPitch   = (mouseY - centerY) * -mouseGain

            # Note that the heading change is applied to the playerNode, while
            # the pitch is applied to the playerHeadNode. You can use the mouse
            # to turn from side to side, which affects your movement, but there
            # is no way to tilt the player upward or downward because you're
            # always standing upright.

            # For heading, just adjust by the appropriate amount.
            self.playerNode.setHpr(self.playerNode, deltaHeading, 0, 0)

            # For pitch, we need to be more careful. If we just call setHpr to
            # adjust the pitch, then Panda3D will apply the full rotation,
            # which means you can wind up facing backwards. But if we then call
            # getP() to get the pitch, it will still return a value between -90
            # and 90, which means we can't fix it up after the fact. Instead,
            # add the delta to the pitch outside of Panda3D, so that we can
            # detect and fix the case where the player has tried to look too
            # high or low (by capping them to just under 90 degrees in either
            # direction).
            newPitch = self.playerHeadNode.getP() + deltaPitch
            newPitch = constrainToInterval(newPitch, -89, 89)
            self.playerHeadNode.setP(newPitch)

        return Task.cont

    def clicked(self):
        ball = self.loader.loadModel("smiley")
        ball.reparentTo(self.render)
        ball.setScale(0.02)
        ball.setPos(self.playerNode.getPos() + self.playerHeadNode.getPos())
        ball.setHpr(self.playerNode.getHpr())


if __name__ == "__main__":
    main()

