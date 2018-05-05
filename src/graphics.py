from src.logconfig import newLogger
from src.main import app

log = newLogger(__name__)

# MOVE-TO: graphics.py
def toggleSmileyFrowney():
    if not app.smileyIsFrowney:
        app.smileyModel.detachNode()
        app.frowneyModel.reparentTo(app.smileyNP)
    else:
        app.frowneyModel.detachNode()
        app.smileyModel.reparentTo(app.smileyNP)
    app.smileyIsFrowney = not app.smileyIsFrowney

