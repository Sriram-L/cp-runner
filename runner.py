#!/opt/homebrew/bin/python3
import tomllib
import sys
import argparse
import subprocess
import os
import time
import signal
import tomllib as tom
from rich.console import Console
from rich import print
from rich import box
from rich.table import Table

parser = argparse.ArgumentParser()
#Set arguments
parser.add_argument("path", help = "Path to file")
parser.add_argument('-t','--testcase', default = 'all', help = 'Testcase#')
#Get argument
args = parser.parse_args()
Input = None
filename = os.path.basename(args.path).rsplit(".",1)[0]
input_filename = f"{filename}.toml"
console = Console()

def compiler():
    compile_command = f"g++ -std=c++17 -O2 -o {filename} {args.path}"
    
    with console.status("[bold blue] Compiling...") as status:
        result = subprocess.run(compile_command,shell = True, capture_output = True, text = True)

    if result.returncode == 0:
        print(("[green]>>>\tCompilation success[green]"))
    else:
        print(("[red]>>>\tCompilation error[red]\n"))
        print(result.stderr)
        sys.exit(0)
    
def parser():
    global Input
    with console.status("[bold blue] Parsing...") as status:
        try:
            with open(input_filename,'rb') as file:
                Input = tom.load(file)
            print("[green]>>>\tParsed input[green]")
        except FileNotFoundError:
            print("[red]>>>\tParsing Error[red]\n")
            print("{input_filename} not found")
            sys.exit(0)
        except tom.TOMLDecodeError as e:
            print("[red]\nParsing Error[red]")
            print("Reason: {e}[red]")
            sys.exit(0)
def runner():
    for number,inp in Input.items():
        if args.testcase != "all" and number != args.testcase:
            continue
        run_command = f"./{filename}" 
        out = ""
        Time = None
        timeout = False
        try:
            with console.status(f"[orange] Running {number}") as status:
                start = time.time()                
                result = subprocess.run(run_command, input = inp, shell = True, capture_output = True,text = True,timeout = 5)
                end = time.time()
                Time = f"Time(ms) {(end-start)*1000}"
        except subprocess.TimeoutExpired:
            out = "[red]Time Limit Exceeded" 
            timeout = True
        if timeout == False:
            if result.returncode != 0:
                exit_code = result.returncode
                signal_name = signal.Signals(-(exit_code)).name
                out = "[red]Runtime Error: " + signal_name
            else:
                out = result.stdout
        table = Table(title = number, box = box.ASCII, caption = Time, caption_justify = 'right')
        table.add_column('Input', justify = 'left' , style = 'white',width = 20)
        table.add_column('Output', justify = 'left' , style = 'white',width = 20)
        table.add_row(inp,out)
        console.print(table)
if __name__ == "__main__":
#Clear screen
    subprocess.run("clear",shell = True)    
    print(r"""[blue]\   __________  ____                             
  / ____/ __ \/ __ \__  ______  ____  ___  _____
 / /   / /_/ / /_/ / / / / __ \/ __ \/ _ \/ ___/
/ /___/ ____/ _, _/ /_/ / / / / / / /  __/ /    
\____/_/   /_/ |_|\__,_/_/ /_/_/ /_/\___/_/     
                                                
          [blue]""")
#Compiling binary
    compiler()
    
#Parsing input data
    parser()
    
#Running against test cases
    runner()
    

