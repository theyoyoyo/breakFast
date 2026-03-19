import { useState, useRef, useCallback } from 'react'

const SpeechRecognition =
  window.SpeechRecognition || window.webkitSpeechRecognition

/**
 * Web Speech API hook.
 * Returns:
 *   - isListening: bool
 *   - startListening(onResult): begin STT; calls onResult(transcript) when done
 *   - stopListening(): stop STT
 *   - speak(text): TTS
 *   - supported: bool — whether the browser supports the API
 */
export function useVoice() {
  const [isListening, setIsListening] = useState(false)
  const recognitionRef = useRef(null)
  const supported = !!SpeechRecognition

  const startListening = useCallback((onResult) => {
    if (!supported) return
    if (recognitionRef.current) recognitionRef.current.abort()

    const recognition = new SpeechRecognition()
    recognition.lang = navigator.language || 'en-US'
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript
      onResult(transcript)
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [supported])

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop()
    setIsListening(false)
  }, [])

  const speak = useCallback((text) => {
    if (!window.speechSynthesis) return
    window.speechSynthesis.cancel()
    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = 1.0
    utterance.pitch = 1.0
    window.speechSynthesis.speak(utterance)
  }, [])

  return { isListening, startListening, stopListening, speak, supported }
}
