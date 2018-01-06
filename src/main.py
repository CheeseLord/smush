from direct.showbase.ShowBase import ShowBase

def main():
    app = MyApp()
    app.run()

class MyApp(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)

if __name__ == "__main__":
    main()

