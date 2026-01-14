
import os
import google.generativeai as genai
from dotenv import load_dotenv

def test_api_key():
    print("Loading environment variables...")
    load_dotenv()
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment variables.")
        return

    print(f"✅ Found GOOGLE_API_KEY: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        genai.configure(api_key=api_key)
        
        print("\nTesting model listing...")
        models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        print(f"✅ Available models: {models}")
        
        model_name = 'gemini-1.5-flash' # Fallback if 2.5 is not available or correct name
        # Check if we can find a flash model
        flash_models = [m for m in models if 'flash' in m]
        if flash_models:
            model_name = flash_models[0]
            
        print(f"\nTesting generation with {model_name}...")
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Hello, can you hear me?")
        
        print(f"✅ Response received: {response.text}")
        print("\n🎉 API Key is working correctly!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    test_api_key()
