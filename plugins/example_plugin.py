def hello(args):
    print("Hello from plugin!")


def register(registry):
    registry.register("hello", hello, "Test plugin command")
