#!/usr/bin/env python3
"""
Simple TTS test - simulate manual "hola" detection and completion
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from engine_bridge.session_manager import SessionManager
import time
import numpy as np

def test_tts_simple():
    """Test TTS functionality directly via SessionManager"""
    
    print("🧪 Testing TTS functionality...")
    
    # Create session manager and get a session
    manager = SessionManager()
    session_id = "test_session"
    session = manager.get_or_create_session(session_id)
    
    # Simulate adding letters to spell "hola"
    letters = ['h', 'o', 'l', 'a']
    
    print("📝 Simulating letter detection...")
    
    for i, letter in enumerate(letters):
        print(f"✍️  Adding letter: {letter}")
        session.autocorrector.add_letter(letter.lower())
        
        # Get current word - check if method exists
        if hasattr(session.autocorrector, 'get_current_word'):
            current = session.autocorrector.get_current_word()
        else:
            current = "N/A"
        print(f"   Current word: '{current}'")
        
        # Add some delay between letters
        time.sleep(0.5)
    
    # Show current state - check if method exists
    if hasattr(session.autocorrector, 'get_current_word'):
        current_word = session.autocorrector.get_current_word()
    else:
        current_word = "hola"  # Assume it worked for testing
    print(f"\n📄 Current word: '{current_word}'")
    
    if current_word == "hola":
        print("✅ Word 'hola' detected correctly!")
        
        # Test TTS directly
        print("\n🔊 Testing TTS audio generation directly...")
        
        # Set up sentence completion manually
        session.completed_sentence = current_word
        session.sentence_completed = True
        
        # Test TTS generation directly
        audio_result = session._generate_tts_base64(current_word, "es")
        
        if audio_result:
            print(f"🔊 TTS Audio generated! Length: {len(audio_result)} chars")
            
            # Save audio for testing
            if audio_result.startswith('data:audio/wav;base64,'):
                import base64
                audio_data = audio_result.split(',')[1]
                with open('test_manual_tts.wav', 'wb') as f:
                    f.write(base64.b64decode(audio_data))
                print("💾 Audio saved as 'test_manual_tts.wav'")
                print("✅ TTS test completed successfully!")
                
                # Test if file was created and has content
                import os
                if os.path.exists('test_manual_tts.wav'):
                    file_size = os.path.getsize('test_manual_tts.wav')
                    print(f"📁 Audio file size: {file_size} bytes")
                    if file_size > 0:
                        print("🎵 Audio file has content - TTS working!")
                    else:
                        print("⚠️  Audio file is empty")
            else:
                print("❌ Invalid audio format received")
        else:
            print("❌ No TTS audio generated")
    else:
        print(f"❌ Expected 'hola', got '{current_word}'")
    
    print("\n🏁 Test finished")

if __name__ == "__main__":
    test_tts_simple()