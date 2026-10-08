import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'
afterEach(cleanup)
// jsdom does not implement the native modal dialog lifecycle.
HTMLDialogElement.prototype.showModal=function(){this.setAttribute('open','')}
HTMLDialogElement.prototype.close=function(){this.removeAttribute('open')}
// Media playback is provided by the browser, not jsdom.
HTMLMediaElement.prototype.play=async function(){}
HTMLMediaElement.prototype.pause=function(){}
