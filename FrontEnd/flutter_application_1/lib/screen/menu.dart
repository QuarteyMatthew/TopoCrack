import 'package:flutter/material.dart';

class TopoCrack extends StatelessWidget {
  const TopoCrack({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(
          "TopoCrack",
          style: TextStyle(
                
          ),
        ),
        centerTitle: true,
        
      ),
      body: Center(
        child: Text("Welcome to TopoCrack!"),
      ),

      bottomNavigationBar: BottomAppBar(
        child: Container(
          height: 50.0,
          child: Center(
            
          ),
        ),
      ),
    );
  }
}