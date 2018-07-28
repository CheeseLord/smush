from panda3d.bullet import BulletWorld
from panda3d.core import BitMask32
from panda3d.core import ClockObject
from panda3d.core import CollisionHandlerEvent
from panda3d.core import CollisionTraverser
from panda3d.core import Vec3
from panda3d.physics import PhysicsCollisionHandler

from pandac.PandaModules import loadPrcFileData

from src.graphics import toggleSmileyFrowney
from src.logconfig import newLogger
from src.world_config import GRAVITY_ACCEL

log = newLogger(__name__)

# Each object belongs to zero or more of these groups. The matrix of which
# groups collide with which other groups is defined in initCollisionGroups.
COLLIDE_BIT_GROUND_PLANE = 0
COLLIDE_BIT_SCENERY      = 1 # Floors, walls
COLLIDE_BIT_PLAYER       = 2
COLLIDE_BIT_ENTITY       = 3 # Misc entities flying around
COLLIDE_BIT_BULLET       = 4
    # Bullets are split off from other entities because they don't collide with
    # the player. Really this group is for "things that otherwise collide as
    # entities, except that they don't collide with the player". But I couldn't
    # think of a short name for that.

COLLIDE_MASK_NONE         = BitMask32(0x0)
COLLIDE_MASK_GROUND_PLANE = BitMask32.bit(COLLIDE_BIT_GROUND_PLANE)
COLLIDE_MASK_SCENERY      = BitMask32.bit(COLLIDE_BIT_SCENERY     )
COLLIDE_MASK_PLAYER       = BitMask32.bit(COLLIDE_BIT_PLAYER      )
COLLIDE_MASK_ENTITY       = BitMask32.bit(COLLIDE_BIT_ENTITY      )
COLLIDE_MASK_BULLET       = BitMask32.bit(COLLIDE_BIT_BULLET      )

# Not used yet, but still define it preemptively because we'll probably want
# it.
app = None

world = None

physicsCollisionHandler = None
eventCollisionHandler   = None

def initPhysics(app_):
    global app
    app = app_

    # Allow creating a matrix of Booleans to specify which collision groups
    # collide with which other collision groups.
    loadPrcFileData("", "bullet-filter-algorithm groups-mask")

    global world
    world = BulletWorld()
    world.setGravity(Vec3(0, 0, -GRAVITY_ACCEL))

    app.taskMgr.add(doPhysicsOneFrame, "doPhysics")

    initCollisionGroups()
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

def initCollisionGroups():
    """
    Setup the rules for which collision groups can collide with which other
    collision groups.
    """

    # Note: this matrix is required to be symmetric across the main diagonal: X
    # can collide with Y if and only if Y can collide with X. Therefore, we
    # only specify one half of the matrix.
    #
    #               ground
    #               plane   scenery  player  entity  bullet
    # ground plane    1        0       1       1       1
    # scenery                  0       1       1       1
    # player                           0       1       0
    # entity                                   1       1
    # bullet                                           1

    # TODO: Would this be more readable organized in columns instead of rows?

    world.setGroupCollisionFlag(COLLIDE_BIT_GROUND_PLANE,
                                COLLIDE_BIT_GROUND_PLANE, True)
    world.setGroupCollisionFlag(COLLIDE_BIT_GROUND_PLANE,
                                COLLIDE_BIT_SCENERY,      False)
    world.setGroupCollisionFlag(COLLIDE_BIT_GROUND_PLANE,
                                COLLIDE_BIT_PLAYER,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_GROUND_PLANE,
                                COLLIDE_BIT_ENTITY,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_GROUND_PLANE,
                                COLLIDE_BIT_BULLET,       True)

    world.setGroupCollisionFlag(COLLIDE_BIT_SCENERY,
                                COLLIDE_BIT_SCENERY,      False)
    world.setGroupCollisionFlag(COLLIDE_BIT_SCENERY,
                                COLLIDE_BIT_PLAYER,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_SCENERY,
                                COLLIDE_BIT_ENTITY,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_SCENERY,
                                COLLIDE_BIT_BULLET,       True)

    world.setGroupCollisionFlag(COLLIDE_BIT_PLAYER,
                                COLLIDE_BIT_PLAYER,       False)
    world.setGroupCollisionFlag(COLLIDE_BIT_PLAYER,
                                COLLIDE_BIT_ENTITY,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_PLAYER,
                                COLLIDE_BIT_BULLET,       False)

    world.setGroupCollisionFlag(COLLIDE_BIT_ENTITY,
                                COLLIDE_BIT_ENTITY,       True)
    world.setGroupCollisionFlag(COLLIDE_BIT_ENTITY,
                                COLLIDE_BIT_BULLET,       True)

    world.setGroupCollisionFlag(COLLIDE_BIT_BULLET,
                                COLLIDE_BIT_BULLET,       True)

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
    # TODO[bullet]: This isn't used anymore. Reimplement custom collision
    # detection so we can toggle between smiley and frowney when that object is
    # shot.
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

# TODO[bullet]: Provide a way to get/set the player velocity?

def addBulletColliders(bulletColliderPhys, bulletColliderEvt, physicsNP):
    # Handle collisions through physics via bulletColliderPhys.
    physicsCollisionHandler.addCollider(bulletColliderPhys, physicsNP)
    app.cTrav.addCollider(bulletColliderPhys, physicsCollisionHandler)

    # Handle collisions in custom manner via bulletColliderEvt.
    app.cTrav.addCollider(bulletColliderEvt, eventCollisionHandler)
