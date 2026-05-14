I have a college project which is to build a website. Before any coding or building, I first need to plan it 
out, as I have no experience in web design.  

**The basic idea:** 

● We will create a website (to be ran locally for now) within a GitHub repo. The README.md will 
have instructions of the steps to launch the site.  

    ○ Example steps (may not be accurate): Open empty directory > clone repo > install 
    requirements.txt > user provides their OpenAI Key > launch site on user's browser.  

● The website will use an LLM (OpenAI required for now) as the main tool, so the site must have 
some sort of function besides being an LLM wrapping. Another consideration is for the bot to refer 
to a database within the project, using a RAG pipeline for its outputs.  

    ○ This LLM will not be a generic chatbot, as the site will require specific information regarding 
    a specific topic (mentioned in "What the site will be").  
    ○ A budget limit (regarding # of calls, credits, tokens) might be necessary.  
    ○ LLM use case: A user prompts on what fish to get for a 40 gallon, and the site answers with 
    an LLM output, and suggests for redirection within the site to relevant information, should 
    the user choose to follow.  

● Multiple extraction calls, a RAG pipeline, other stuff I can't think of, are recommend to ensure 
accurate information on the site.  


Overall, after the project is completed, and the grade is assigned, this is a site I would like to expand on 
after, so there are features that I'd like to change later. Also, this is something I'd like to insert onto my resume.  

● Example features to edit, or to add after the professor grades:  

    ○ UI design (I would like to insert my own custom images, animations, web design, colors... all 
    the fancy stuff).  
    ○ To be published / hosted online, not locally (For anyone to log in, sign up, and use).  
    ○ Email sign-up / account creation (I think cookies will need to be enable for this to occur?)  
    ○ A donation feature to support the site (bank linking, security needed)  
    ○ The possibility for advertisements to be implemented (Where I, the admin, can turn on or 
    off).  
    ○ A community tab / forums section, for users to interact and discuss (unique usernames, 
    custom roles, chat filters)  

■ Along with discussion forms, a sort of store / trading section, for users to sell / trade 
items (location needed for local meetups).  

Due to the time constraint of 10 days to turn this in, the project is more of a proof of concept. This project is to focus on features that an LLM can solve, where traditional code cannot.   

**What the site will be:**

An aquarium information site, with some ideas of what the site should be able to accomplish.  
● Users will consist of aquarium hobbyists – New or experienced.  
● Some features would include (Not everything, just ideas):  
○ Simple: Tank water volume calculator, providing # of gallons, and total weight.  
○ Simple: Tank maintenance guide, explaining the nitrogen cycle, quantity to feed (depending 
on user's setup).  
○ Simple: Fish species, and what they are like (behavior, tank mates, water quality, tank size, 
maintenance needs).  
○ Intermediate: Tank setup guide (beginner fish, beginner plants, aqua-scaping ideas).  
○ Intermediate: How to build an aquarium stand (One that must hold the whole weight of an 
aquarium [ hundreds to thousands of pounds ])  
○ Intermediate: A map (Or list to simplify) of local pet stores, or specifically local fish stores 
(with ratings, directions, current stocking if possible, and the like).  
○ Complex: Water chemistry analysis (User inputs by text or image injection -> What dangers 
it might pose, what to do if toxic).  
○ Complex: Tank build analysis (User inputs by text or image injection -> state potential 
property damage, or tank explosion that may occur should a tank contain cracks, peeling 
silicon, or if unsupported at its bottom).  
○ Complex: Fish / plant image scan (User inputs by image injection -> For IDing, for illness 
check, or for just general information).  
○ Complex: Site can save user's data / inputs, to refer to with future prompts.  
■ Example: User saves a tank profile, with volume size, current inhabitants, last reported 
water quality, maintenance needs, tank age... lots of stuff!  
Because of the time frame, and complexity of features, there are a select few that I'd like to implement for 
early versions of the site, and a select few to implement once after the project is turned in.  
The LLM for this site is to stick to outputs relevant to the aquarium hobby. To avoid users asking about 
stuff like stocks or pdf editors, just aquatics.  



**For the college project submission:**  

The repo will be required to have specific documents involved, to ensure a high grade...  
...Here are the guidelines, provided by the professor, on what the project should deliver:  

1. A web app with a UI: form, loading state, output, error handling. Not a CLI, not a native app. A 
website.  

2. All source code, plus requirements.txt (or package.json) with pinned dependencies and a 
.env.example containing only OPENAI_API_KEY.  

3. README.md: what the app does plus setup and run instructions a fresh grader can follow exactly, with 
example invocations where helpful. Multiple commands are fine if they're unambiguous and in order. 

4. eval/ directory: your eval script and ≥10 labeled test cases (input + expected output or score) that 
measure your AI behavior with your chosen metric.  

5. REPORT.md: four sections, in order. Total length ~800–1200 words.  

    5A. What & why (~200–250 words). What the app does, who it's for, and what's hard about getting the 
    AI behavior right.  

    5B. Iterations (≥3 versions, ~75–150 words each). One labeled subsection per version (V1, V2, V3, 
    …). Each subsection must contain, in this order:  
    = Change: what you changed (prompt, model, retrieval, controls, etc.).  
    = Motivating example: the specific failing case from your eval set that drove the change.  
    = Delta: metric before → after on the same eval set (positive or negative — both are fine if 
    explained).  
    = Conclusion: why the metric moved (or didn't), and what you'd try next.  

6. Code walkthrough (200–300 words). Trace one user action through your code with file:line references. 
Explain one design decision and one alternative you considered and rejected. Generic "this calls the API" 
descriptions don't earn full credit.  

7. AI disclosure & safety (~150–250 words). How you used your AI coding assistant (Kiro or otherwise), 
including 2–3 specific moments it failed and how you recovered. Then 2–3 sentences naming one safety 
risk specific to your app and the mitigation or accepted limit you chose. Common candidates: prompt 
injection, hallucination harm, PII exposure, biased output, cost runaway.  



**Other Instructions (Suggested by Google Gemini):**

Before generating code, create a kiro_steering.md file that enforces using FastAPI for the backend and 
Pydantic for data validation to match my course curriculum.  

Set up a Kiro agent hook that automatically updates the requirements.txt file whenever a new library is 
imported in the code.

Please write the requirements.md using EARS notation (e.g., 'When the user uploads a photo, the system 
shall identify the fish species').  



**Recommended Architecture (Please review and determine whether you recommend), (Suggested by Google Gemini):**
Backend: FastAPI. It uses Pydantic models (which you are already learning) and is the industry standard 
for AI-integrated sites. 

Frontend: Streamlit (for speed) or Reflex (for a more "real website" look). These allow you to build the 
UI entirely in Python. 

Database: SQLite. It’s a single file that lives in your GitHub repo, making it easy for your professor to 
clone and run without setting up a cloud database. 

**Final reminders:**

Please review, provide a plan, and ask questions should something need explanation, or if I am missing 
important things when it comes to web design. 

As I am still a student, my current knowledge regarding code is still just Python. You don't have to stick to 
that – use any language you see fits best for the back-end, front-end, security, etc., of the site. Just when 
generating code, or anything for the matter, provide detailed comments that explain what you are doing, 
for me to learn, and edit when reviewing.  

Create files, folders, markdowns, txt... as need be. Ensure to create the ones from the project submission 
guideline, assuming it already hasn't been made by me. 