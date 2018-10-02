"use strict";

/*
 * Display video from the webcam
 */

navigator.mediaDevices.getUserMedia({video: true})
.then(function(localMediaStream) {
    var video = document.querySelector('video');
    video.srcObject = localMediaStream;
    video.onloadedmetadata = function(e) {
        video.play();
    };
})
.catch(function(e) {
    console.log('WebCam access rejected by the user!', e);
});
