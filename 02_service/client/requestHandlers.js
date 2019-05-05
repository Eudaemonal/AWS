"use strict"

const fs = require('fs')
const formidable = require('formidable')
const util = require('util')

function start(request, response) {
    console.log('Request handler start was called')
    let fileName = './index.html'
    responseHTML(response, fileName)
}

function upload(request, response) {
    console.log('Request handler upload was called')

    var upload_path = "uploaded/"
    var oldpath = ""
    var newpath = ""
    var form = new formidable.IncomingForm()
    form.parse(request, function (error, fields, files) {
        oldpath = files.filetoupload.path
        newpath = upload_path + "file.pdf"
        // copy the file to a new location
        fs.rename(oldpath, newpath, function (err) {
            if (err) throw err
        });
    });

    let fileName = "./download.html"
    downloadHTML(response, fileName, newpath)
}

function downloadHTML(response, fileName, downloadpath) {
    fs.readFile(fileName, 'utf8', function onReturn(error, data) {
        if(error) throw error
        response.statusCode = 200
        response.setHeader('Content-Type', 'text/html')
        response.write(data)
        response.end()
    })
}

function download(request, response) {
    console.log('Request handler download was called')

    response.setHeader('Content-Type', 'application/pdf')
    fs.createReadStream("./uploaded/file.pdf").pipe(response)
}

function responseHTML(response, fileName) {
    fs.readFile(fileName, 'utf8', function onReturn(error, data) {
        if(error) throw error
        response.statusCode = 200
        response.setHeader('Content-Type', 'text/html')
        response.write(data)
        response.end()
    })
}

//Public API
module.exports = {
    'start': start,
    'upload': upload,
    'download': download
}