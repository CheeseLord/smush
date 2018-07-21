from panda3d.bullet import BulletWorld
from panda3d.core import BitMask32
from panda3d.core import ClockObject
from panda3d.core import CollisionHandlerEvent
from panda3d.core import CollisionTraverser
from panda3d.core import Vec3
from panda3d.physics import PhysicsCollisionHandler

from src import graphics # FIXME[#2]

from src.graphics import toggleSmileyFrowney
from src.logconfig import newLogger
from src.world_config import GRAVITY_ACCEL

log = newLogger(__name__)

# Bitmasks for the "into" colliders
# TODO: Remove "INTO_" from these names? It makes them kind of needlessly long,
# especially since we don't have any COLLIDE_MASK_FROMs...
COLLIDE_MASK_INTO_NONE   = BitMask32(0x0)
COLLIDE_MASK_INTO_FLOOR  = BitMask32(0x1)
COLLIDE_MASK_INTO_WALL   = BitMask32(0x2)
COLLIDE_MASK_INTO_PLAYER = BitMask32(0x4)
COLLIDE_MASK_INTO_ENTITY = BitMask32(0x8) # For misc entities flying around

# Not used yet, but still define it preemptively because we'll probably want
# it.
app = None

world = None

physicsCollisionHandler = None
eventCollisionHandler   = None

def initPhysics(app_):
    global app
    app = app_

    global world
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -GRAVITY_ACCEL))

    app.taskMgr.add(doPhysicsOneFrame, "doPhysics")

    initCollisionHandling()

def doPhysicsOneFrame(task):
    # TODO: This next line doesn't lint, but maybe it would be more efficient
    # to cache the globalClock somehow instead of calling getGlobalClock()
    # every frame? I suppose we could just suppress the pylint warning.
    # dt = globalClock.getDt()
    dt = ClockObject.getGlobalClock().getDt()
    # TODO[#3] This seems excessive but until we fix recoil lets leave this
    # here for debugging purposes
    # 90 substeps, at 1/600 frames per second for physics updates.
    world.doPhysics(dt, 90, 1.0/600.0)
    return task.cont

def initCollisionHandling():
    """
    Initialize the collision handlers. This must be run before any objects are
    created.
    """

    global physicsCollisionHandler
    global eventCollisionHandler

    # Note: app already has a cTrav before this line, but its set to the value
    # 0. So we are not defining a new member outside of __init__; we're just
    # overwriting an existing one.
    app.cTrav = CollisionTraverser()

    # Handle fast objects
    app.cTrav.setRespectPrevTransform(True)

    # TODO[#2]: Have physics.py expose a function to add colliders
    # Used to handle collisions between physics-affected objects.
    physicsCollisionHandler = PhysicsCollisionHandler()

    # Used to run custom code on collisions.
    eventCollisionHandler = CollisionHandlerEvent()

    eventCollisionHandler.addInPattern("%fn-into-%in")
    eventCollisionHandler.addOutPattern("%fn-out-%in")

    # TODO[#2]: These don't belong here... where do they belong? initWorld?
    app.accept("BulletColliderEvt-into-SmileyCollide", onCollideEventIn)
    app.accept("BulletColliderEvt-out-SmileyCollide",  onCollideEventOut)

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

def getPlayerVel():
    return getPlayerPhysicsObj().getVelocity()

def setPlayerVel(newVel):
    getPlayerPhysicsObj().setVelocity(newVel)

def getPlayerPhysicsObj():
    return graphics.playerNP.node().getPhysicsObject()

def addBulletColliders(bulletColliderPhys, bulletColliderEvt, physicsNP):
    # Handle collisions through physics via bulletColliderPhys.
    physicsCollisionHandler.addCollider(bulletColliderPhys, physicsNP)
    app.cTrav.addCollider(bulletColliderPhys, physicsCollisionHandler)

    # Handle collisions in custom manner via bulletColliderEvt.
    app.cTrav.addCollider(bulletColliderEvt, eventCollisionHandler)
