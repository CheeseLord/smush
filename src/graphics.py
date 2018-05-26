from src.logconfig import newLogger

log = newLogger(__name__)

app = None # pylint: disable=invalid-name

smileyIsFrowney = False # pylint: disable=invalid-name
smileyNP     = None # pylint: disable=invalid-name
smileyModel  = None # pylint: disable=invalid-name
frowneyModel = None # pylint: disable=invalid-name

def initGraphics(theApp):
    global app # pylint: disable=invalid-name
    app = theApp

def toggleSmileyFrowney():
    global smileyIsFrowney # pylint: disable=invalid-name
    if not smileyIsFrowney:
        smileyModel.detachNode()
        frowneyModel.reparentTo(smileyNP)
    else:
        frowneyModel.detachNode()
        smileyModel.reparentTo(smileyNP)
    smileyIsFrowney = not smileyIsFrowney

