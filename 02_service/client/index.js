"use strict"

const server = require("./server.js")
const router = require("./router.js")
const requestHandlers = require("./requestHandlers.js")

let handler = {}
handler["/"] = requestHandlers.start
handler["/start"] = requestHandlers.start
handler["/upload"] = requestHandlers.upload
handler["/download"] = requestHandlers.download

server.start(router.route, handler)