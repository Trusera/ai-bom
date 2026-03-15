from crewai.flow import Flow, start, listen, router


class MyFlow(Flow):
    @start()
    def begin(self):
        return "started"

    @listen(begin)
    def process(self, data):
        return "processed"

    @router(process)
    def route(self, data):
        return "route_a"
