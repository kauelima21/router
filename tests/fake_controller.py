class FakeController:
    def index(self, request, response):
        return response.status(200).json({"handler": "index"})

    def create(self, request, response):
        return response.status(201).json({"handler": "create"})
