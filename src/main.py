from direct.showbase.ShowBase import ShowBase
from panda3d.core import CollisionTraverser

from src.control import initControl
from src.graphics import initGraphics
from src.logconfig import enableDebugLogging
from src.logconfig import newLogger
from src.physics import initPhysics
from src.world import initWorld

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

    app.run()

    # Not reached; I think Panda3D calls sys.exit when you close the window.
    log.info("End.")


def initModules(app):
    initPhysics(app)
    initControl(app)
    initGraphics(app)
    initWorld(app)


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


if __name__ == "__main__":
    main()
