import sys

from direct.showbase.ShowBase import ShowBase
from direct.task import Task

def main():
    app = MyApp()
    app.run()

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

        # Mapping of keys currently pressed (key name : bool). Populated in
        # setupEventHandlers.
        self.keys = {}

        self.playerNode = self.render.attachNewNode("Player")
        self.playerHeadNode = self.playerNode.attachNewNode("PlayerHead")
        self.playerHeadNode.setPos(0, 0, 1)
        self.camera.reparentTo(self.playerHeadNode)
        self.disableMouse()
        self.setupEventHandlers()
        self.taskMgr.add(self.updatePlayerPosTask, "UpdatePlayerPosTask")

    def setupEventHandlers(self):
        def pushKey(key, value):
            self.keys[key] = value

        for key in ["w", "a", "s", "d", "q", "e"]:
            self.keys[key] = False
            self.accept(key, pushKey, [key, True])
            self.accept("%s-up" % key, pushKey, [key, False])
            # WaRTS had this line, but it seems a little sketchy to me...
            # shouldn't we like note the modifier or something?
            # self.accept("shift-%s" % key, pushKey, [key, True])

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

        moveFwd   = self.keys["w"]
        moveLeft  = self.keys["a"]
        moveRight = self.keys["d"]
        moveBack  = self.keys["s"]

        rightDelta = (moveRight - moveLeft) * sidewaysSpeed * dt
        fwdDelta = 0
        if moveFwd and not moveBack:
            fwdDelta = forwardSpeed * dt
        elif moveBack and not moveFwd:
            fwdDelta = -backwardSpeed * dt

        self.playerNode.setPos(self.playerNode, rightDelta, fwdDelta, 0)

        return Task.cont


if __name__ == "__main__":
    main()

