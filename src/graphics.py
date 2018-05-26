from panda3d.core import Point3

from src.logconfig import newLogger
from src.utils import constrainToInterval

log = newLogger(__name__)

app = None # pylint: disable=invalid-name

playerNP     = None # pylint: disable=invalid-name
playerHeadNP = None # pylint: disable=invalid-name

smileyIsFrowney = False # pylint: disable=invalid-name
smileyNP     = None # pylint: disable=invalid-name
smileyModel  = None # pylint: disable=invalid-name
frowneyModel = None # pylint: disable=invalid-name

def initGraphics(app_):
    global app # pylint: disable=invalid-name
    app = app_

def toggleSmileyFrowney():
    global smileyIsFrowney # pylint: disable=invalid-name
    if not smileyIsFrowney:
        smileyModel.detachNode()
        frowneyModel.reparentTo(smileyNP)
    else:
        frowneyModel.detachNode()
        smileyModel.reparentTo(smileyNP)
    smileyIsFrowney = not smileyIsFrowney

def getRelativePlayerVector(vector):
    """
    Convert vector from the player's coordinate system to the render's
    coordinate system.
    """

    return app.render.getRelativeVector(playerNP, vector)

def getRelativePlayerHeadVector(vector):
    """
    Convert vector from the player's head's coordinate system to the render's
    coordinate system.
    """

    return app.render.getRelativeVector(playerHeadNP, vector)

# TODO[#2]: This and getPlayerVel should be in the same module. Probably
# physics.  And probably it should use the physics node instead of the graphics
# node.
def getPlayerPos():
    return playerNP.getPos()

# TODO[#2]: Uh... not sure we can move this one to physics. What do??
def getPlayerHeadPos():
    return app.render.getRelativePoint(playerHeadNP, Point3(0, 0, 0))

def getPlayerHeadingPitch():
    heading = playerNP.getH()
    pitch   = playerHeadNP.getP()
    return (heading, pitch)

def changePlayerHeadingPitch(deltaHeading, deltaPitch):
    # Note that the heading change is applied to the playerNP, while
    # the pitch is applied to the playerHeadNP. You can use the mouse
    # to turn from side to side, which affects your movement, but there
    # is no way to tilt the player upward or downward because you're
    # always standing upright.

    # For heading, just adjust by the appropriate amount.
    playerNP.setHpr(playerNP, deltaHeading, 0, 0)

    # For pitch, we need to be more careful. If we just call setHpr to
    # adjust the pitch, then Panda3D will apply the full rotation,
    # which means you can wind up facing backwards. But if we then call
    # getP() to get the pitch, it will still return a value between -90
    # and 90, which means we can't fix it up after the fact. Instead,
    # add the delta to the pitch outside of Panda3D, so that we can
    # detect and fix the case where the player has tried to look too
    # high or low (by capping them to just under 90 degrees in either
    # direction).
    newPitch = playerHeadNP.getP() + deltaPitch
    newPitch = constrainToInterval(newPitch, -89, 89)
    playerHeadNP.setP(newPitch)

