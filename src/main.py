from direct.showbase.ShowBase import ShowBase

def main():
    app = MyApp()
    app.run()

class MyApp(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

        # Load the environment model.
        self.scene = self.loader.loadModel("models/environment")
        self.scene.reparentTo(self.render)

        # Apply scale and position transforms on the model.
        # Something something magic numbers bad something something.
        self.scene.setScale(0.25, 0.25, 0.25)
        self.scene.setPos(-8, 42, 0)

if __name__ == "__main__":
    main()

