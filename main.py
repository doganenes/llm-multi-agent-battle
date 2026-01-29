import argparse
from game import run_game

if __name__ == "__main__":
   # initialize the command line parser 
    parser = argparse.ArgumentParser(prog="Simulation runner" ,description="Skyrowar Multi-Agent Battle Simulation")
    
    # add arguments to parser
    parser.add_argument("--model-a",type=str, default="gpt-4o", help="LLM model for Team A")
    parser.add_argument("--model-b",type=str, default="gpt-4o-mini", help="LLM model for Team B")
    parser.add_argument("--episodes",type=int, default=5, help="Number of episodes to run")
    parser.add_argument("--difficulty",type=float, default=1.0, help="Difficulty scaling for Team B")

    # parse the command line arguments 
    args = parser.parse_args()
    print("Initializing Multi-Agent Battle Simulation...")
    # call run_game function to start multi-agent battle simulation
    run_game(model_a=args.model_a,
             model_b=args.model_b,
             num_episodes=args.episodes,
             difficulty=args.difficulty)