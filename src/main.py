import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task
from panda3d.core import WindowProperties  # pylint: disable=no-name-in-module

from src.logconfig import newLogger

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
        self.taskMgr.add(self.updatePlayerPosTask, "UpdatePlayerPosTask")

    def setupEventHandlers(self):
        # Provide a way to exit even when we make the window fullscreen.
        self.accept('control-q', sys.exit)

        # Camera toggle.
        # self.accept("f3",       self.toggleCameraStyle, [])

        # Handle window close request (clicking the X, Alt-F4, etc.)
        # self.win.set_close_request_event("window-close")
        # self.accept("window-close", self.handleWindowClose)

    # We don't use task, but we can't remove it because the function signature
    # is from Panda3D.
    def updatePlayerPosTask(self, task):  # pylint: disable=unused-argument
        dt = self.globalClock.getDt()

        forwardSpeed  = 20
        sidewaysSpeed = 15
        backwardSpeed = 10

        # See:
        #     https://www.panda3d.org/manual/index.php/Keyboard_Support
        # section "Polling interface"
        moveFwd   = self.mouseWatcherNode.is_button_down("w")
        moveLeft  = self.mouseWatcherNode.is_button_down("a")
        moveRight = self.mouseWatcherNode.is_button_down("d")
        moveBack  = self.mouseWatcherNode.is_button_down("s")

        rightDelta = (moveRight - moveLeft) * sidewaysSpeed * dt
        fwdDelta = 0
        if moveFwd and not moveBack:
            fwdDelta = forwardSpeed * dt
        elif moveBack and not moveFwd:
            fwdDelta = -backwardSpeed * dt

        self.playerNode.setPos(self.playerNode, rightDelta, fwdDelta, 0)

        return Task.cont

    def controlCamera(self, task):  # pylint: disable=unused-argument
        # TODO: Actually control the camera.
        self.win.movePointer(
            0,
            self.win.getXSize() / 2,
            self.win.getYSize() / 2,
        )

        return Task.cont


if __name__ == "__main__":
    main()

