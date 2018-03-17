def constrainToInterval(val, low, high):
    return max(low, min(val, high))

def moveVectorTowardByAtMost(fromVec, toVec, maxDelta):
    """
    Return the vector which is obtained by moving from fromVec toward toVec by
    a total distance of maxDelta. If the distance from fromVec to toVec is less
    than maxDelta, return toVec.
    """

    assert maxDelta >= 0
    if maxDelta == 0:
        return fromVec

    vecDelta = toVec - fromVec
    if vecDelta.length() < maxDelta:
        return toVec
    else:
        # Since maxDelta > 0 and vecDelta.length() !< maxDelta,
        # vecDelta.length() can't be 0, so it's safe to divide by it.
        vecDelta *= maxDelta / vecDelta.length()
        return fromVec + vecDelta

