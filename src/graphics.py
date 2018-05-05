from src.logconfig import newLogger

log = newLogger(__name__)

app = None # pylint: disable=invalid-name

def initGraphics(theApp):
    global app # pylint: disable=invalid-name
    app = theApp

def toggleSmileyFrowney():
    if not app.smileyIsFrowney:
        app.smileyModel.detachNode()
        app.frowneyModel.reparentTo(app.smileyNP)
    else:
        app.frowneyModel.detachNode()
        app.smileyModel.reparentTo(app.smileyNP)
    app.smileyIsFrowney = not app.smileyIsFrowney

