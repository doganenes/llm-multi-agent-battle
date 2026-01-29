import time
import math        
from agents import TeamGenerationAgent, TeamManagerAgent, TeamLeadAgent

# ANSI color codes for logging hallucinations and errors
RED = "\033[91m"
RESET = "\033[0m"

def apply_difficulty_scaling(team_data, difficulty_ratio):
    """
    Scales a team's stats (health and attack power)
    Formula: New_Stats = Old_Stats * sqrt(Difficulty)
    """
    if  difficulty_ratio == 1.0:
        return team_data
    
    scaling_factor = math.sqrt(difficulty_ratio)
    print(f"[SYSTEM] Applying Difficulty {difficulty_ratio}x (Factor: {scaling_factor:.2f}) to Team B")
    for hero_name, stats in team_data.items():
        stats["initial_health"] = int(400 * scaling_factor)
        stats["initial_attack_power"] = int(200 * scaling_factor)
    
    return team_data
    
def perform_turn(active_manager, active_lead, passive_manager, passive_lead, active_name, passive_name):
    """
    Executes a single turn for one team.
    
    Args:
        active_manager: The Manager of the attacking team.
        active_lead: The lead of the attacking team.
        passive_manager: The Manager of the defending team.
        passive_lead: The Lead of the defending team.
        active_name: String name of attacking team.
        passive_name: String name of defending team.
    
    Returns:
        str: "GAME OVER" if the game ends, otherwise "CONTINUE".
    """
    
    print(f"\n>>> {active_name} is acting...")
    
    # manager selects hero & skill
    # manager decides who attacks and how (using active sklill or buff)
    manager_decision = active_manager.select_hero_for_turn()    
    if manager_decision is None: 
        print(f"{RED}[{active_name}] MANAGER FAILED (Returned None). Turn aborted.{RESET}")
        return None
    
    
    # checking for manager error
    if manager_decision.get("status") == "ERROR":
        print(f"{RED}[{active_name}] MANAGER CRITICAL ERROR. Turn aborted.{RESET}")
        return None

    # checking intenal action: if Infight/Buff was used, trun ends
    if manager_decision.get("status") == "INTERNAL ACTION":
        print(f"[{active_name}] performed an internal maneuver. Turn ends.")
        return "CONTINUE"
    
    # team lead decides which target to aim and guesses identity
    attack_payload = active_lead.get_turn_decision(manager_decision)
    
    if attack_payload is None:
        # this usually happens if the Manager failed to provide attack payload 
        # in correct format, or team lead failed to parse
        print(f"{RED}[{active_name}] Team Lead failed to decide.{RESET}")
        return None
    
    # check for surrender
    if attack_payload.get("action") == "SURRENDER":
        print(f"\n!!! {active_name} HAS DECLARED SURRENDER. {passive_name} WINS! !!!")
        return "GAME OVER"
    
    # standard attack execution if not surrendered
    print(f"[{active_name} Lead] Sending Attack -> Pos {attack_payload['target_position']} (Guess: {attack_payload['guessed_identity']})")
    feedback = passive_lead.receive_hostile_attack(attack_payload, passive_manager)
    
    # check for defender processing failure 
    if  feedback is None:
        print(f"{RED}[{passive_name}] DEFENDER FAILED to process attack (Returned). Turn Invalid.{RESET}")
        return None
        
    # if the defender triggered "Counter" or "Explode", the attacker takes damage back
    counter_damage = feedback.get("counter_damage")
    if counter_damage > 0:
        print(f"[{active_name}] RECOIL! Taking {counter_damage} counter-damage.")
        attacker_id = manager_decision.get("selected_hero_id")
        if attacker_id is not None:
            active_manager.update_hero_stats(attacker_id, counter_damage)
        else:
            print(f"{RED}[{active_name}] MANAGER HALLUCINATED: Missing attacker_id during Recoil. Turn aborter.{RESET}")
            return None
            
    active_lead.update_intel(attack_payload["target_position"], feedback)
    # update collateral casualities (redirects/AOE/Global damage)
    for dead_pos in feedback["all_dead_positions"]:
        # explicitly marking them as dead with 0 health
        # to prevent the Team Lead from attacking them next turn
        active_lead.update_intel(dead_pos, {"target_status": "dead", "target_health": 0})
    
    # If guessed correctly, the Team Lead Learns the identity for future turns
    if feedback.get("guess_correct"):
        print(f"[{active_name}] TACTICAL SUCCESS! Enemy identity confirmed.")                    
    
    else:
        print(f"[{active_name}] Guess failed.")
        
        
    return "CONTINUE"
    
def get_total_team_health(manager):
    """Calculates sum of health of all heroes in the team."""
    return sum(h["health"] for h in manager.my_team.values())
    
def get_alive_count(manager):
    """Counts alive heroes."""
    return len([h for h in manager.my_team.values() if h["status"] == "alive"])


def calculate_metrics(results, team_label):
    """
    Calculates Win Rate, Damage Rate, and Final Reward Score
    """
    total_games = len(results)
    
    # 1. Win Rate
    wins = sum(1 for r in results if r["winner"] == team_label)
    win_rate = wins / total_games

    # 2. Damage Rate
    # damage_dealt_by_a or damage_dealt_by_b
    damage_key = f"damage_dealt_by_{team_label.split(" ")[1].lower()}"
    total_damage = sum(r[damage_key] for r in results)
    avg_damage = total_damage / total_games
    damage_rate = avg_damage / 1600.0
    
    # 3. Reward Score
    # Reward = 0.7 * WinRate + 0.3 * Damage Rate
    reward = (0.7 * win_rate) + (0.3 * damage_rate) 

    return win_rate, damage_rate, reward, wins


def run_game_loop(model_a, model_b, difficulty=1.0):
    print("=========================================")
    print("     SYROWAR: MULTI-AGENT BATTLE GAME    ")
    print("=========================================")
    
    # PHASE 1: TEAM GENERATION
    team_gen_agent_a = TeamGenerationAgent("A", model_a)
    team_gen_agent_b = TeamGenerationAgent("B", model_b)
    
    team_a_data = team_gen_agent_a.generate_team()
    team_b_data = team_gen_agent_b.generate_team()
    
    if not team_a_data:
        print(f"{RED}Team Generation Agent A Failed to generate a valid team !!!{RESET}")
        return None    
    
    if not team_b_data:
        print(f"{RED}Team Generation Agent B Failed to generate a valid team !!!{RESET}")
        return None    
    
    # apply difficulty scaling to Team B before team manager initialization
    if difficulty != 1.0:
        team_b_data = apply_difficulty_scaling(team_b_data, difficulty)
    
    # PHASE 2: TEAM MANAGER INITIALIZATION
    manager_a = TeamManagerAgent("A", model_a)
    manager_a.initialize_team(team_a_data)
    manager_b = TeamManagerAgent("B", model_b)
    manager_b.initialize_team(team_b_data)
    
    # PHASE 3: TEAM LEAD INITIALIZATION
    lead_a = TeamLeadAgent("Team A", model_a)
    lead_b = TeamLeadAgent("Team B", model_b)
    
    # PHASE 4: BATTLE
    turn_counter = 1
    game_running = True
    winner = "Draw"
    
    print("\n============= BATTLE START =============")
    
    while game_running:
        print(f"\n--- ROUND {turn_counter} ---")
        
        # Team A turn
        result = perform_turn(manager_a, lead_a, manager_b, lead_b, "Team A", "Team B")
        if result is None:
            print(f"{RED}Error when performing turn (Team A crash) !!{RESET}")
            return None # Stop the episode immediately to record failure
            
        if result == "GAME OVER":
            winner = "Team B"
            break
        
        time.sleep(1)
        
        result = perform_turn(manager_b, lead_b, manager_a, lead_a, "Team B", "Team A")
        if result is None:
            print(f"{RED}Error when peforming turn (Team B crash) !!{RESET}")
            return None
            
        if result == "GAME OVER":
            winner = "Team A"
            break
    
        turn_counter += 1
    
    # --- POST GAME STATS ---
    # Victory condition is having more heroes alive at the end of the game
    alive_a = get_alive_count(manager_a)
    alive_b = get_alive_count(manager_b)
    
    if alive_a > alive_b:
        winner = "Team A"
    elif alive_b > alive_a:
        winner = "Team B"
    else:
        winner = "Draw"
    
    # damage rate calculation
    start_hp_a = 1600 # 4 heroes * 400 HP
    start_hp_b = int(1600 * math.sqrt(difficulty))if difficulty != 1.0 else 1600
     
    damage_dealt_by_a = start_hp_b - get_total_team_health(manager_b)
    damage_dealt_by_b = start_hp_a - get_total_team_health(manager_a)
    
    print(f"\n=== GAME OVER ===")
    print(f"Winner: {winner}")
    print(f"Alive: A({alive_a}) vs B({alive_b})")
    print(f"Damage Dealt: A({damage_dealt_by_a}) - B({damage_dealt_by_b})")
    
    return {
        "winner": winner,
        "damage_dealt_by_a": damage_dealt_by_a,
        "damage_dealt_by_b": damage_dealt_by_b
    }
    
# function to simulate multi-agent battle game and 
# display calculated metrics for given `num_episodes`    
def run_multi_agent_battle_simulation(model_a, model_b, num_episodes, difficulty=1.0):
    print(f"Starting Battle Simulation ({num_episodes} Episodes)...")
    results = []
    
    start_time = time.time()
    
    for i in range(num_episodes):
        print(f"Running Episode {i+1}...")
        stats = run_game_loop(model_a, model_b, difficulty)
        
        if stats is not None:
            results.append(stats)
        else:
            print(f"{RED}Episode {i+1} Failed due to Agent Error/Crash (Skipped).{RESET}")
        
        
    total_time = time.time() - start_time    
    print(f"\nSimulation Complete in {total_time:.2f}s\n")
    
    if not results:
        print(f"{RED}No valid games were completed.{RESET}")
        return
    
    # Calculating metrics for both teams
    win_rate_a, damage_rate_a, reward_a, wins_a = calculate_metrics(results, "Team A")
    win_rate_b, damage_rate_b, reward_b, wins_b = calculate_metrics(results, "Team B")
    
    # Displaying metrics
    print(f"{'METRIC':<40} | {'TEAM A':<17} | {'TEAM B':<40}")
    print("-" * 86)
    print(f"Number of wins out of {num_episodes} {'rounds':<17}| {wins_a} |  {wins_b:<38}")
    print(f"{'Win Rate':<40} | {win_rate_a:.2%}            |  {win_rate_b:.2%}")
    print(f"{'Avg Damage Rate':<40} | {damage_rate_a:.2%}            | {damage_rate_b:.2%}")
    print("-" * 86)  
    print(f"{'FINAL REWARD SCORE':<40} | {reward_a:.4f}            | {reward_b:.4f}")
    print("-" * 86)
    
    # interpreting results
    if reward_a > reward_b:
        print(">> RESULT: Team A outperforms Team B.")
    elif reward_b > reward_a:
        print(">> RESULT: Team B outperforms Team A.")
    else: 
        print(">> RESULT: Performance is balanced.")
        
# function to run the game
def run_game(model_a, model_b, num_episodes, difficulty):
    # number of episodes can be adjusted for statistical significance
    # model_a="gemini-2.5-pro", model_b="gemini-2.5-flash",num_episodes=5, difficulty=1.0
    run_multi_agent_battle_simulation(model_a=model_a, 
                                      model_b=model_b, 
                                      num_episodes=num_episodes, 
                                      difficulty=difficulty)
